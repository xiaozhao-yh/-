"""管理端：数据看板 / 用户管理 / AI模型配置 / Prompt模板 / AI历史记录"""
import time
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import get_db, require_admin
from ..models import AiConfig, AiHistory, PromptTemplate, Resume, User
from ..schemas import (
    AiConfigIn,
    HistoryOut,
    Page,
    PromptCreateIn,
    PromptUpdateIn,
    UserCreateIn,
    UserOut,
    UserUpdateIn,
)
from ..security import hash_password

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

VALID_SCENES = {"score", "analysis", "suggestion", "rewrite", "interview", "chat"}


# ---------- 系统首页 / 数据看板 ----------
@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    user_count = db.query(User).filter(User.role == "user").count()
    total_user_count = db.query(User).count()
    resume_count = db.query(Resume).count()
    ai_call_count = db.query(AiHistory).count()
    failed_calls = db.query(AiHistory).filter(AiHistory.status == "failed").count()
    fail_rate = round(failed_calls / ai_call_count * 100, 1) if ai_call_count else 0.0

    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_calls = db.query(AiHistory).filter(AiHistory.created_at >= today).count()

    type_stats, model_stats = {}, {}
    for rec in db.query(AiHistory.type, AiHistory.model).all():
        type_stats[rec.type] = type_stats.get(rec.type, 0) + 1
        m = rec.model or "未知"
        model_stats[m] = model_stats.get(m, 0) + 1

    trend = []
    start = today - timedelta(days=6)
    rows = db.query(AiHistory.created_at).filter(AiHistory.created_at >= start).all()
    counts = {}
    for (created,) in rows:
        day = created.strftime("%m-%d")
        counts[day] = counts.get(day, 0) + 1
    for i in range(7):
        d = (today + timedelta(days=i - 6))
        key = d.strftime("%m-%d")
        trend.append({"date": key, "count": counts.get(key, 0)})

    recent = (
        db.query(AiHistory, User.username)
        .join(User, AiHistory.user_id == User.id)
        .order_by(AiHistory.id.desc())
        .limit(8)
        .all()
    )
    recent_items = [
        {
            "id": rec.id, "username": username, "resume_title": rec.resume_title,
            "type": rec.type, "model": rec.model, "score": rec.score,
            "duration_ms": rec.duration_ms, "created_at": rec.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        for rec, username in recent
    ]

    return {
        "user_count": user_count,
        "total_user_count": total_user_count,
        "resume_count": resume_count,
        "ai_call_count": ai_call_count,
        "today_calls": today_calls,
        "failed_calls": failed_calls,
        "fail_rate": fail_rate,
        "type_stats": [{"name": k, "value": v} for k, v in type_stats.items()],
        "model_stats": [{"name": k, "value": v} for k, v in model_stats.items()],
        "trend": trend,
        "recent": recent_items,
    }


# ---------- 用户信息管理 ----------
@router.get("/users")
def list_users(page: int = 1, page_size: int = 10, keyword: str = "", db: Session = Depends(get_db)):
    q = db.query(User)
    if keyword.strip():
        kw = f"%{keyword.strip()}%"
        q = q.filter((User.username.like(kw)) | (User.nickname.like(kw)) | (User.email.like(kw)))
    total = q.count()
    items = q.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size,
            "items": [UserOut.model_validate(u).model_dump() for u in items]}


@router.post("/users")
def create_user(data: UserCreateIn, db: Session = Depends(get_db)):
    username = data.username.strip()
    if not (2 <= len(username) <= 30):
        raise HTTPException(status_code=400, detail="用户名长度需为 2-30 个字符")
    if len(data.password) < 6:
        raise HTTPException(status_code=400, detail="密码至少 6 位")
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="用户名已存在")
    if data.role not in ("user", "admin"):
        raise HTTPException(status_code=400, detail="角色不合法")
    user = User(
        username=username,
        password_hash=hash_password(data.password),
        nickname=data.nickname.strip() or username,
        email=data.email.strip(),
        phone=data.phone.strip(),
        role=data.role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return UserOut.model_validate(user).model_dump()


@router.put("/users/{user_id}")
def update_user(user_id: int, data: UserUpdateIn, db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if data.nickname is not None:
        user.nickname = data.nickname.strip()
    if data.email is not None:
        user.email = data.email.strip()
    if data.phone is not None:
        user.phone = data.phone.strip()
    if data.role is not None:
        if data.role not in ("user", "admin"):
            raise HTTPException(status_code=400, detail="角色不合法")
        if user.id == user_id and user.role == "admin" and data.role != "admin":
            raise HTTPException(status_code=400, detail="不能降级自己的管理员角色")
        user.role = data.role
    if data.password:
        if len(data.password) < 6:
            raise HTTPException(status_code=400, detail="密码至少 6 位")
        user.password_hash = hash_password(data.password)
    db.commit()
    return UserOut.model_validate(user).model_dump()


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail="不能删除自己的账号")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin" and db.query(User).filter(User.role == "admin").count() <= 1:
        raise HTTPException(status_code=400, detail="至少保留一个管理员账号")
    db.query(AiHistory).filter(AiHistory.user_id == user_id).delete()
    db.query(Resume).filter(Resume.user_id == user_id).delete()
    db.delete(user)
    db.commit()
    return {"ok": True}


# ---------- AI 模型配置 ----------
def _mask_key(key: str) -> str:
    if not key:
        return ""
    return key[:6] + "****" + key[-4:] if len(key) > 12 else "****"


@router.get("/ai-configs")
def list_ai_configs(db: Session = Depends(get_db)):
    items = db.query(AiConfig).order_by(AiConfig.id.desc()).all()
    out = []
    for c in items:
        d = {
            "id": c.id, "provider": c.provider, "base_url": c.base_url,
            "api_key": _mask_key(c.api_key), "model_name": c.model_name,
            "is_enabled": c.is_enabled, "remark": c.remark,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }
        out.append(d)
    return out


@router.post("/ai-configs")
def create_ai_config(data: AiConfigIn, db: Session = Depends(get_db)):
    if not data.api_key.strip():
        raise HTTPException(status_code=400, detail="API Key 不能为空")
    cfg = AiConfig(
        provider=data.provider.strip(),
        base_url=data.base_url.strip(),
        api_key=data.api_key.strip(),
        model_name=data.model_name.strip(),
        is_enabled=False,
        remark=data.remark.strip(),
    )
    db.add(cfg)
    db.commit()
    return {"ok": True, "id": cfg.id}


@router.put("/ai-configs/{config_id}")
def update_ai_config(config_id: int, data: AiConfigIn, db: Session = Depends(get_db)):
    cfg = db.get(AiConfig, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    cfg.provider = data.provider.strip()
    cfg.base_url = data.base_url.strip()
    cfg.model_name = data.model_name.strip()
    cfg.remark = data.remark.strip()
    # 未修改 Key（脱敏占位或为空）时保留原 Key
    if data.api_key.strip() and "****" not in data.api_key:
        cfg.api_key = data.api_key.strip()
    db.commit()
    return {"ok": True}


@router.post("/ai-configs/{config_id}/toggle")
def toggle_ai_config(config_id: int, db: Session = Depends(get_db)):
    cfg = db.get(AiConfig, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    if not cfg.is_enabled and not cfg.api_key:
        raise HTTPException(status_code=400, detail="请先填写 API Key 再启用")
    cfg.is_enabled = not cfg.is_enabled
    db.commit()
    return {"ok": True, "is_enabled": cfg.is_enabled}


@router.delete("/ai-configs/{config_id}")
def delete_ai_config(config_id: int, db: Session = Depends(get_db)):
    cfg = db.get(AiConfig, config_id)
    if not cfg:
        raise HTTPException(status_code=404, detail="配置不存在")
    db.delete(cfg)
    db.commit()
    return {"ok": True}


# ---------- Prompt 模板管理 ----------
@router.get("/prompts")
def list_prompts(
    page: int = 1,
    page_size: int = 10,
    name: str = "",
    code: str = "",
    scene: str = "",
    status: int = -1,  # -1全部 0停用 1启用
    db: Session = Depends(get_db),
):
    q = db.query(PromptTemplate)
    if name.strip():
        q = q.filter(PromptTemplate.name.like(f"%{name.strip()}%"))
    if code.strip():
        q = q.filter(PromptTemplate.code.like(f"%{code.strip()}%"))
    if scene:
        q = q.filter(PromptTemplate.scene == scene)
    if status == 0:
        q = q.filter(PromptTemplate.status == False)  # noqa: E712
    elif status == 1:
        q = q.filter(PromptTemplate.status == True)  # noqa: E712
    total = q.count()
    items = q.order_by(PromptTemplate.id.asc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total, "page": page, "page_size": page_size,
        "items": [
            {"id": p.id, "code": p.code, "name": p.name, "scene": p.scene,
             "content": p.content, "status": bool(p.status),
             "updated_at": p.updated_at.strftime("%Y-%m-%d %H:%M:%S")}
            for p in items
        ],
    }


@router.get("/prompts-all")
def prompts_all(db: Session = Depends(get_db)):
    """筛选项用：全部模板（含停用）"""
    items = db.query(PromptTemplate).order_by(PromptTemplate.id.asc()).all()
    return [
        {"id": p.id, "code": p.code, "name": p.name, "scene": p.scene, "status": bool(p.status)}
        for p in items
    ]


@router.post("/prompts")
def create_prompt(data: PromptCreateIn, db: Session = Depends(get_db)):
    code = data.code.strip().upper()
    name = data.name.strip()
    if not code:
        raise HTTPException(status_code=400, detail="模板编码不能为空")
    if not name:
        raise HTTPException(status_code=400, detail="模板名称不能为空")
    if data.scene not in VALID_SCENES:
        raise HTTPException(status_code=400, detail="适用场景不合法")
    if not data.content.strip():
        raise HTTPException(status_code=400, detail="Prompt 内容不能为空")
    if db.query(PromptTemplate).filter(PromptTemplate.code == code).first():
        raise HTTPException(status_code=400, detail=f"模板编码 {code} 已存在")
    tpl = PromptTemplate(code=code, name=name, scene=data.scene, content=data.content, status=data.status)
    db.add(tpl)
    db.commit()
    return {"ok": True, "id": tpl.id}


@router.put("/prompts/{prompt_id}")
def update_prompt(prompt_id: int, data: PromptUpdateIn, db: Session = Depends(get_db)):
    tpl = db.get(PromptTemplate, prompt_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    if data.code is not None:
        code = data.code.strip().upper()
        if not code:
            raise HTTPException(status_code=400, detail="模板编码不能为空")
        dup = db.query(PromptTemplate).filter(PromptTemplate.code == code, PromptTemplate.id != prompt_id).first()
        if dup:
            raise HTTPException(status_code=400, detail=f"模板编码 {code} 已存在")
        tpl.code = code
    if data.name is not None:
        if not data.name.strip():
            raise HTTPException(status_code=400, detail="模板名称不能为空")
        tpl.name = data.name.strip()
    if data.scene is not None:
        if data.scene not in VALID_SCENES:
            raise HTTPException(status_code=400, detail="适用场景不合法")
        tpl.scene = data.scene
    if data.content is not None:
        if not data.content.strip():
            raise HTTPException(status_code=400, detail="模板内容不能为空")
        tpl.content = data.content
    if data.status is not None:
        tpl.status = data.status
    db.commit()
    return {"ok": True}


@router.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    tpl = db.get(PromptTemplate, prompt_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="模板不存在")
    db.delete(tpl)
    db.commit()
    return {"ok": True}


@router.post("/prompts/batch-delete")
def batch_delete_prompts(data: dict, db: Session = Depends(get_db)):
    ids = [i for i in (data.get("ids") or []) if isinstance(i, int)]
    if not ids:
        raise HTTPException(status_code=400, detail="请选择要删除的模板")
    n = db.query(PromptTemplate).filter(PromptTemplate.id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    return {"ok": True, "deleted": n}


# ---------- AI 历史记录 ----------
@router.get("/ai-histories")
def list_ai_histories(
    page: int = 1,
    page_size: int = 10,
    user_id: int = 0,
    resume_title: str = "",
    model: str = "",
    prompt_code: str = "",
    type: str = "",
    db: Session = Depends(get_db),
):
    q = db.query(AiHistory, User.username).join(User, AiHistory.user_id == User.id)
    if user_id:
        q = q.filter(AiHistory.user_id == user_id)
    if resume_title.strip():
        q = q.filter(AiHistory.resume_title.like(f"%{resume_title.strip()}%"))
    if model.strip():
        q = q.filter(AiHistory.model.like(f"%{model.strip()}%"))
    if prompt_code:
        q = q.filter(AiHistory.prompt_code == prompt_code)
    if type:
        q = q.filter(AiHistory.type == type)
    total = q.count()
    rows = q.order_by(AiHistory.id.desc()).offset((page - 1) * page_size).limit(page_size).all()
    items = []
    for rec, username in rows:
        items.append({
            "id": rec.id, "user_id": rec.user_id, "username": username,
            "resume_id": rec.resume_id, "resume_title": rec.resume_title,
            "prompt_code": rec.prompt_code, "type": rec.type, "model": rec.model,
            "score": rec.score, "level": rec.level, "duration_ms": rec.duration_ms,
            "status": rec.status, "created_at": rec.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        })
    return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/ai-histories/{history_id}")
def get_ai_history(history_id: int, db: Session = Depends(get_db)):
    rec = db.get(AiHistory, history_id)
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    user = db.get(User, rec.user_id)
    d = HistoryOut.model_validate(rec).model_dump()
    d["username"] = user.username if user else ""
    return d


@router.get("/users-all")
def users_all(db: Session = Depends(get_db)):
    """筛选项用：全部用户下拉"""
    items = db.query(User.id, User.username, User.nickname).order_by(User.id.asc()).all()
    return [{"id": u.id, "username": u.username, "nickname": u.nickname} for u in items]
