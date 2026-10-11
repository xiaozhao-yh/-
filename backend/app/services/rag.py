"""RAG 检索层：知识库 embedding（懒生成）+ 余弦相似度 top-k 检索 + prompt 注入

轻量实现说明：向量以 JSON 形式存储在 knowledge_chunks.embedding 列，检索为纯 Python 余弦相似度；
接口与 FAISS/Chroma 同构（embed → index → search），数据量增大时可平滑替换为向量数据库。
embedding 失败/无配置时优雅降级：返回空列表，不阻塞 AI 主流程。
"""
import json
import math

from sqlalchemy.orm import Session

from ..models import AiConfig, KnowledgeChunk
from ..seed_data import KB_CHUNKS

EMBED_MODEL = "text-embedding-v3"  # DashScope 兼容模式 embedding 模型
TOP_K = 3
MIN_SCORE = 0.30                   # 相似度阈值，低于则不注入
BATCH = 6                          # embeddings 批量大小


def _embed_client(cfg: AiConfig):
    from openai import OpenAI
    return OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=60)


def embed_texts(cfg: AiConfig, texts: list) -> list:
    """调用 OpenAI 兼容 embeddings 接口（分批）"""
    client = _embed_client(cfg)
    vecs = []
    for i in range(0, len(texts), BATCH):
        resp = client.embeddings.create(model=EMBED_MODEL, input=texts[i:i + BATCH])
        vecs.extend([d.embedding for d in resp.data])
    return vecs


def ensure_seed(db: Session):
    """首次使用时写入知识库种子片段"""
    if db.query(KnowledgeChunk).count() == 0:
        for c in KB_CHUNKS:
            db.add(KnowledgeChunk(title=c["title"], content=c["content"], tag=c.get("tag", "")))
        db.commit()


def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def search(db: Session, cfg, query: str, top_k: int = TOP_K) -> list:
    """top-k 检索，返回 [{'title','snippet','score'}]；任何异常均返回 []"""
    try:
        ensure_seed(db)
        rows = db.query(KnowledgeChunk).filter(KnowledgeChunk.enabled == True).all()  # noqa: E712
        if not rows or not cfg or not cfg.api_key:
            return []
        missing = [r for r in rows if not r.embedding]
        if missing:
            vecs = embed_texts(cfg, [r.content for r in missing])
            for r, v in zip(missing, vecs):
                r.embedding = json.dumps(v)
            db.commit()
        qv = embed_texts(cfg, [query[:2000]])[0]
        scored = []
        for r in rows:
            try:
                v = json.loads(r.embedding)
            except Exception:
                continue
            if len(v) == len(qv):
                scored.append((_cosine(qv, v), r))
        scored.sort(key=lambda t: t[0], reverse=True)
        return [
            {"title": r.title, "snippet": r.content[:120], "score": round(s, 3)}
            for s, r in scored[:top_k] if s >= MIN_SCORE
        ]
    except Exception:
        return []


def build_query(resume, scene: str) -> str:
    """用简历要点 + 岗位 + 场景关键词构造检索 query"""
    scene_kw = {
        "score": "评分标准 诊断",
        "analysis": "问题分析 常见误区",
        "suggestion": "优化建议 量化表达",
        "rewrite": "经历改写 STAR",
        "interview": "面试准备 深挖",
        "chat": "优化建议 改写",
    }.get(scene, "")
    return (f"目标岗位：{resume.target_position}；JD：{(resume.job_desc or '')[:200]}；"
            f"简历要点：{(resume.current_text or '')[:400]}；{scene_kw}")


def build_kb_message(refs: list):
    """把检索结果拼成可注入 messages 的 system 消息（标注来源标题）"""
    if not refs:
        return None
    lines = "\n".join(f"- 【{r['title']}】{r['snippet']}" for r in refs)
    return {"role": "system",
            "content": "以下是来自知识库的参考资料（已标注来源），供回答时酌情引用，不要编造资料之外的结论：\n" + lines}
