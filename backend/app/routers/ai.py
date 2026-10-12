"""AI 能力：诊断评分 / 问题分析(SSE) / 优化建议(SSE) / 简历改写与采纳 / 模拟面试题 / 多轮助手对话 / 历史记录

- 所有 AI 端点支持可选 body：{config_id, prompt_id} 指定模型配置与 Prompt 模板；缺省用默认启用项。
- RAG：每次调用前对知识库做 top-k 向量检索，参考资料以 system 消息注入 prompt，
  来源（标题+相似度）通过 SSE refs 事件 / 响应 references 字段返回前端标注，并落库 AiHistory.refs。
- 多轮对话：/chat 接口接收前端 history，服务端校验角色、裁剪轮次与长度后构造 messages。
"""
import json
import time

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..deps import get_current_user, get_db
from ..models import AiConfig, AiHistory, PromptTemplate, Resume, User
from ..schemas import AiOptionsIn, ChatIn, HistoryOut, RewriteAdoptIn
from ..routers.resumes import get_own_resume
from ..services import rag
from ..services.llm import (
    LlmError,
    build_messages,
    chat_once,
    elapsed_ms,
    extract_json,
    get_active_config,
    get_prompt,
    iter_stream,
)

router = APIRouter(prefix="/ai", tags=["ai"])

VALID_LEVELS = {"优秀", "良好", "合格", "待改进"}
MAX_HISTORY_TURNS = 8       # 多轮对话最多携带的历史消息数
MAX_TURN_CHARS = 1500       # 单条历史消息最大长度


def _save_history(db: Session, user: User, resume: Resume, cfg, scene: str, prompt_code: str,
                  output: str, duration: int, score=None, level="", refs=None, status: str = "success") -> AiHistory:
    rec = AiHistory(
        user_id=user.id,
        resume_id=resume.id if resume else None,
        resume_title=resume.title if resume else "",
        prompt_code=prompt_code,
        type=scene,
        model=cfg.model_name if cfg else "",
        input_text=f"目标岗位：{resume.target_position if resume else ''}｜JD：{(resume.job_desc if resume else '')[:200]}｜简历摘要：{(resume.current_text if resume else '')[:1500]}",
        output_text=(output or "")[:60000],
        refs=json.dumps(refs or [], ensure_ascii=False),
        score=score,
        level=level or "",
        duration_ms=duration,
        status=status,
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _kb(db: Session, cfg, resume, scene: str):
    """RAG 检索：返回 (可注入的 system 消息, refs)"""
    refs = rag.search(db, cfg, rag.build_query(resume, scene))
    return rag.build_kb_message(refs), refs


def _with_kb(messages: list, kb_msg):
    if kb_msg:
        return [messages[0], kb_msg] + messages[1:]
    return messages


def _stream_ai(user: User, resume: Resume, scene: str, config_id=None, prompt_id=None,
               temperature: float = 0.6):
    """SSE 生成器：start → refs(RAG来源) → delta... → done，结果统一落库（含失败记录）"""
    def gen():
        db = SessionLocal()
        cfg = None
        tpl = None
        start = time.time()
        try:
            yield _sse_event({"start": True})
            cfg = get_active_config(db, config_id)
            tpl = get_prompt(db, scene, prompt_id)
            kb_msg, refs = _kb(db, cfg, resume, scene)
            yield _sse_event({"refs": refs})
            messages = _with_kb(
                build_messages(tpl.content, resume.current_text, resume.target_position, resume.job_desc),
                kb_msg,
            )
            buf = []
            for piece in iter_stream(cfg, messages, temperature):
                buf.append(piece)
                yield _sse_event({"delta": piece})
            output = "".join(buf)
            rec = _save_history(db, user, resume, cfg, scene, tpl.code, output, elapsed_ms(start), refs=refs)
            yield _sse_event({"done": True, "record_id": rec.id, "duration_ms": rec.duration_ms})
        except LlmError as e:
            _save_failed(db, user, resume, cfg, scene, tpl, str(e), start)
            yield _sse_event({"error": str(e)})
        except Exception as e:
            msg = f"AI 服务异常：{e}"
            _save_failed(db, user, resume, cfg, scene, tpl, msg, start)
            yield _sse_event({"error": msg})
        finally:
            db.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


def _save_failed(db: Session, user: User, resume: Resume, cfg, scene: str, tpl, err: str, start: float):
    """AI 调用失败也落库（status=failed），供管理端统计失败率；二次异常不阻塞错误返回"""
    try:
        db.rollback()
        _save_history(db, user, resume, cfg, scene, tpl.code if tpl else "",
                      f"调用失败：{err}", elapsed_ms(start), status="failed")
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass


@router.get("/options")
def ai_options(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """可选的模型配置与 Prompt 模板（仅启用项）"""
    configs = [
        {"id": c.id, "provider": c.provider, "model_name": c.model_name}
        for c in db.query(AiConfig).filter(AiConfig.is_enabled == True).order_by(AiConfig.id.desc()).all()  # noqa: E712
    ]
    prompts = [
        {"id": p.id, "name": p.name, "code": p.code, "scene": p.scene}
        for p in db.query(PromptTemplate)
        .filter(PromptTemplate.status == True)  # noqa: E712
        .order_by(PromptTemplate.id.asc()).all()
    ]
    return {"configs": configs, "prompts": prompts}


@router.post("/resumes/{resume_id}/score")
def score_resume(resume_id: int, options: AiOptionsIn = None,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = get_own_resume(resume_id, user, db)
    try:
        cfg = get_active_config(db, options.config_id if options else None)
        tpl = get_prompt(db, "score", options.prompt_id if options else None)
        kb_msg, refs = _kb(db, cfg, resume, "score")
        messages = _with_kb(
            build_messages(tpl.content, resume.current_text, resume.target_position, resume.job_desc), kb_msg)
        start = time.time()
        output = chat_once(cfg, messages, temperature=0.3)
        data = extract_json(output)
        score = int(round(float(data.get("score", 0))))
        score = max(0, min(100, score))
        level = str(data.get("level", "")).strip()
        if level not in VALID_LEVELS:
            level = "优秀" if score >= 85 else "良好" if score >= 70 else "合格" if score >= 55 else "待改进"
        analysis = str(data.get("analysis", "")).strip() or "暂无诊断分析"
    except LlmError as e:
        raise HTTPException(status_code=502, detail=str(e))
    rec = _save_history(db, user, resume, cfg, "score", tpl.code,
                        json.dumps(data, ensure_ascii=False), elapsed_ms(start), score=score, level=level, refs=refs)
    return {"score": score, "level": level, "analysis": analysis, "references": refs, "record_id": rec.id}


@router.post("/resumes/{resume_id}/analysis")
def analysis_resume(resume_id: int, options: AiOptionsIn = None,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = get_own_resume(resume_id, user, db)
    return _stream_ai(user, resume, "analysis",
                      options.config_id if options else None,
                      options.prompt_id if options else None, temperature=0.5)


@router.post("/resumes/{resume_id}/suggestion")
def suggestion_resume(resume_id: int, options: AiOptionsIn = None,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = get_own_resume(resume_id, user, db)
    return _stream_ai(user, resume, "suggestion",
                      options.config_id if options else None,
                      options.prompt_id if options else None, temperature=0.5)


@router.post("/resumes/{resume_id}/rewrite")
def rewrite_resume(resume_id: int, options: AiOptionsIn = None,
                   user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = get_own_resume(resume_id, user, db)
    return _stream_ai(user, resume, "rewrite",
                      options.config_id if options else None,
                      options.prompt_id if options else None, temperature=0.4)


@router.post("/resumes/{resume_id}/chat")
def chat_resume(resume_id: int, data: ChatIn,
                user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """多轮助手对话：服务端校验并裁剪 history 后构造 messages，SSE 输出"""
    resume = get_own_resume(resume_id, user, db)
    return _stream_chat(user, resume, data, data.config_id, data.prompt_id)


def _trim_history(history) -> list:
    """服务端裁剪：角色白名单、单条限长、只保留最近 MAX_HISTORY_TURNS 条"""
    turns = []
    for t in history or []:
        role = t.get("role", "") if isinstance(t, dict) else getattr(t, "role", "")
        content = (t.get("content", "") if isinstance(t, dict) else getattr(t, "content", "")) or ""
        if role in ("user", "assistant") and content.strip():
            turns.append({"role": role, "content": content.strip()[:MAX_TURN_CHARS]})
    return turns[-MAX_HISTORY_TURNS:]


def _stream_chat(user: User, resume: Resume, data: ChatIn, config_id=None, prompt_id=None):
    question = (data.question or "").strip()[:2000]

    def gen():
        db = SessionLocal()
        cfg = None
        tpl = None
        start = time.time()
        try:
            yield _sse_event({"start": True})
            cfg = get_active_config(db, config_id)
            tpl = get_prompt(db, "chat", prompt_id)
            kb_msg, refs = _kb(db, cfg, resume, "chat")
            yield _sse_event({"refs": refs})
            system = build_messages(tpl.content, resume.current_text, resume.target_position, resume.job_desc)
            messages = _with_kb(system, kb_msg)
            for t in _trim_history(data.history):
                messages.append({"role": t["role"], "content": t["content"]})
            messages.append({"role": "user", "content": question})
            buf = []
            for piece in iter_stream(cfg, messages, temperature=0.6):
                buf.append(piece)
                yield _sse_event({"delta": piece})
            output = "".join(buf)
            rec = _save_history(db, user, resume, cfg, "chat", tpl.code,
                                f"问：{question}\n答：{output}", elapsed_ms(start), refs=refs)
            yield _sse_event({"done": True, "record_id": rec.id, "duration_ms": rec.duration_ms})
        except LlmError as e:
            _save_failed(db, user, resume, cfg, "chat", tpl, str(e), start)
            yield _sse_event({"error": str(e)})
        except Exception as e:
            msg = f"AI 服务异常：{e}"
            _save_failed(db, user, resume, cfg, "chat", tpl, msg, start)
            yield _sse_event({"error": msg})
        finally:
            db.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no", "Connection": "keep-alive"},
    )


@router.post("/rewrite/adopt")
def adopt_rewrite(data: RewriteAdoptIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rec = db.get(AiHistory, data.history_id)
    if not rec or rec.user_id != user.id or rec.type != "rewrite":
        raise HTTPException(status_code=404, detail="改写记录不存在")
    if not rec.resume_id:
        raise HTTPException(status_code=400, detail="该记录未关联简历，无法采纳")
    resume = get_own_resume(rec.resume_id, user, db)
    if not rec.output_text.strip():
        raise HTTPException(status_code=400, detail="改写结果为空，无法采纳")
    resume.current_text = rec.output_text
    db.commit()
    db.refresh(resume)
    return {"ok": True, "resume": ResumeOut_model(resume)}


def ResumeOut_model(resume: Resume):
    from ..schemas import ResumeOut
    return ResumeOut.model_validate(resume).model_dump()


@router.post("/resumes/{resume_id}/interview")
def interview_questions(resume_id: int, options: AiOptionsIn = None,
                        user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    resume = get_own_resume(resume_id, user, db)
    try:
        cfg = get_active_config(db, options.config_id if options else None)
        tpl = get_prompt(db, "interview", options.prompt_id if options else None)
        kb_msg, refs = _kb(db, cfg, resume, "interview")
        messages = _with_kb(
            build_messages(tpl.content, resume.current_text, resume.target_position, resume.job_desc), kb_msg)
        start = time.time()
        output = chat_once(cfg, messages, temperature=0.6)
        data = extract_json(output)
        categories = data.get("categories")
        if not isinstance(categories, list) or not categories:
            raise LlmError("模型返回的面试题格式不正确，请重试")
        clean = []
        for c in categories:
            if isinstance(c, dict) and c.get("name") and isinstance(c.get("questions"), list):
                qs = [str(q) for q in c["questions"] if str(q).strip()][:8]
                if qs:
                    clean.append({"name": str(c["name"]), "questions": qs})
    except LlmError as e:
        raise HTTPException(status_code=502, detail=str(e))
    rec = _save_history(db, user, resume, cfg, "interview", tpl.code,
                        json.dumps({"categories": clean}, ensure_ascii=False), elapsed_ms(start), refs=refs)
    return {"categories": clean, "references": refs, "record_id": rec.id}


@router.get("/histories")
def my_histories(
    page: int = 1,
    page_size: int = 10,
    type: str = "",
    resume_id: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(AiHistory).filter(AiHistory.user_id == user.id)
    if type:
        q = q.filter(AiHistory.type == type)
    if resume_id:
        q = q.filter(AiHistory.resume_id == resume_id)
    total = q.count()
    items = (
        q.order_by(AiHistory.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size,
            "items": [HistoryOut.model_validate(i).model_dump() for i in items]}
