"""RAG 检索层：知识库 embedding（懒生成）+ 两阶段检索（关键词重叠预筛 → embedding 余弦重排）+ prompt 注入

轻量实现说明：向量以 JSON 形式存储在 knowledge_chunks.embedding 列，检索为纯 Python 余弦相似度；
接口与 FAISS/Chroma 同构（embed → index → search），数据量增大时可平滑替换为向量数据库。
embedding 失败/无配置时优雅降级：返回空列表，不阻塞 AI 主流程。

两阶段检索：
  1. 关键词重叠预筛：统计 query 和 chunk 的关键词（按非中文字符/标点切分 + 中文单字 bigram）重叠数，
     取候选集 TOP_K_PRE * 10 条（默认 30），避免纯 embedding 将语义无关但向量偶然相近的片段误召回。
  2. embedding 余弦相似度重排：对候选集做 embedding，取 TOP_K 条，阈值 MIN_SCORE 过滤。
  最终 score = 0.3 * norm_keyword + 0.7 * norm_embedding（归一化加权）。
"""
import json
import math
import re

from sqlalchemy.orm import Session

from ..models import AiConfig, KnowledgeChunk
from ..seed_data import KB_CHUNKS

EMBED_MODEL = "text-embedding-v3"  # DashScope 兼容模式 embedding 模型
BATCH = 6                          # embeddings 批量大小
TOP_K_PRE_MULT = 10                # 预筛候选数 = TOP_K * 此倍率


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
    """首次使用时写入知识库种子片段（含默认 created_by='seed'）"""
    if db.query(KnowledgeChunk).count() == 0:
        for c in KB_CHUNKS:
            db.add(KnowledgeChunk(
                title=c["title"], content=c["content"], tag=c.get("tag", ""),
                source_url=c.get("source_url", ""), source_id=c.get("source_id", ""),
                offset=c.get("offset", 0), created_by=c.get("created_by", "seed"),
            ))
        db.commit()


def _cosine(a: list, b: list) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _tokenize(text: str) -> set:
    """轻量中文分词：英文/数字按空格/标点切，中文取单字 bigram（相邻两字），取并集"""
    if not text:
        return set()
    # 英文/数字 token
    ascii_tokens = set(re.findall(r'[A-Za-z][A-Za-z0-9_\-]{1,}', text.lower()))
    # 中文 bigram（相邻两字）+ 单字
    cn_chars = re.findall(r'[\u4e00-\u9fff]', text)
    cn_bigrams = {''.join(cn_chars[i:i + 2]) for i in range(len(cn_chars) - 1)} if len(cn_chars) >= 2 else set()
    cn_singles = set(cn_chars)
    return ascii_tokens | cn_bigrams | cn_singles


def _keyword_overlap(query: str, chunk_text: str) -> int:
    """query 与 chunk 的关键词重叠数（bigram 权重 ×2，其他权重 ×1）"""
    q_ascii, q_bigram, q_single = set(), set(), set()
    for t in re.findall(r'[A-Za-z][A-Za-z0-9_\-]{1,}', query.lower()):
        q_ascii.add(t)
    q_cn = re.findall(r'[\u4e00-\u9fff]', query)
    q_bigram = {''.join(q_cn[i:i + 2]) for i in range(len(q_cn) - 1)} if len(q_cn) >= 2 else set()
    q_single = set(q_cn)
    if not q_ascii and not q_bigram and not q_single:
        return 0

    c_ascii, c_bigram, c_single = set(), set(), set()
    for t in re.findall(r'[A-Za-z][A-Za-z0-9_\-]{1,}', chunk_text.lower()):
        c_ascii.add(t)
    c_cn = re.findall(r'[\u4e00-\u9fff]', chunk_text)
    c_bigram = {''.join(c_cn[i:i + 2]) for i in range(len(c_cn) - 1)} if len(c_cn) >= 2 else set()
    c_single = set(c_cn)

    score = len(q_ascii & c_ascii) + len(q_bigram & c_bigram) * 2 + len(q_single & c_single)
    return score


def search(db: Session, cfg, query: str, top_k: int = None) -> list:
    """两阶段检索：关键词重叠预筛 → embedding 余弦重排 → 阈值过滤

    参数：
        cfg: AiConfig，kb_top_k/kb_min_score 生效；None 时走默认值
        query: 检索 query（简历要点 + 场景关键词拼装）
    返回：
        [{'title','snippet','score','source_url','source_id','created_by'}]，任何异常均返回 []
    """
    try:
        ensure_seed(db)
        rows = db.query(KnowledgeChunk).filter(KnowledgeChunk.enabled == True).all()  # noqa: E712
        if not rows or not cfg or not cfg.api_key:
            return []

        effective_top_k = top_k or getattr(cfg, "kb_top_k", 3) or 3
        min_score = getattr(cfg, "kb_min_score", 0.30) or 0.30
        pre_count = effective_top_k * TOP_K_PRE_MULT

        # --- 阶段 1：关键词重叠预筛 ---
        q_ascii = set(re.findall(r'[A-Za-z][A-Za-z0-9_\-]{1,}', query.lower()))
        q_cn = re.findall(r'[\u4e00-\u9fff]', query)
        q_bigram = {''.join(q_cn[i:i + 2]) for i in range(len(q_cn) - 1)} if len(q_cn) >= 2 else set()
        q_single = set(q_cn)

        if q_ascii or q_bigram or q_single:
            kw_scored = [(_keyword_overlap(query, r.content), r) for r in rows]
            kw_scored.sort(key=lambda t: t[0], reverse=True)
            # 取 top pre_count 候选；若关键词重叠全为 0，退化为全量 embedding
            candidates = kw_scored[:pre_count]
            if candidates[0][0] == 0:
                candidates = [(0, r) for r in rows]
        else:
            candidates = [(0, r) for r in rows]

        # --- 阶段 2：embedding 余弦相似度重排 ---
        missing = [r for _, r in candidates if not r.embedding]
        if missing:
            vecs = embed_texts(cfg, [r.content for r in missing])
            for r, v in zip(missing, vecs):
                r.embedding = json.dumps(v)
            db.commit()
        qv = embed_texts(cfg, [query[:2000]])[0]

        kw_max = max((s for s, _ in candidates), default=0) or 1.0

        final = []
        for kw_score, r in candidates:
            try:
                v = json.loads(r.embedding)
            except Exception:
                continue
            if len(v) != len(qv):
                continue
            emb_score = _cosine(qv, v)
            kw_norm = kw_score / kw_max if kw_max > 0 else 0.0
            fused = 0.3 * kw_norm + 0.7 * emb_score  # 归一化加权
            final.append((fused, emb_score, r))

        final.sort(key=lambda t: t[0], reverse=True)
        return [
            {
                "title": r.title,
                "snippet": r.content[:120],
                "score": round(fused, 3),
                "embedding_score": round(emb, 3),
                "source_url": r.source_url or "",
                "source_id": r.source_id or "",
                "created_by": r.created_by or "",
            }
            for fused, emb, r in final[:effective_top_k] if fused >= min_score
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
    lines = []
    for r in refs:
        src = r.get("source_url") or r.get("source_id") or ""
        ref = f"（来源：{src}）" if src else ""
        lines.append(f"- 【{r['title']}】{r['snippet']}{ref}")
    return {"role": "system",
            "content": "以下是来自知识库的参考资料（已标注来源），供回答时酌情引用，不要编造资料之外的结论：\n" + "\n".join(lines)}
