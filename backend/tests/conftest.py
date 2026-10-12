"""pytest fixture：SQLite in-memory，完全隔离 MySQL 依赖"""
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "..")

from app.database import Base
from app import models as m  # noqa: F401 — 触发模型注册到 Base.metadata

TEST_DB_URL = "sqlite://"  # 内存库


@pytest.fixture(scope="session")
def engine():
    e = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db(engine):
    """每个测试独立事务，用完回滚"""
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def sample_cfg(db):
    """一条最小可用 AiConfig（假 API Key 足够让流程走到 embedding 前）"""
    cfg = m.AiConfig(
        provider="test", base_url="http://test", api_key="fake-key",
        model_name="test-model", is_enabled=True,
        kb_top_k=3, kb_min_score=0.30,
    )
    db.add(cfg)
    db.commit()
    db.refresh(cfg)
    return cfg


@pytest.fixture
def sample_chunk(db):
    """一条带 embedding 的 KnowledgeChunk"""
    chunk = m.KnowledgeChunk(
        title="STAR 法则改写",
        content="STAR 法则改写项目经历，情境任务行动结果四段式。",
        tag="经历改写",
        source_url="", source_id="", offset=0, created_by="seed",
        embedding="",  # 测试里会 mock embedding
        enabled=True,
    )
    db.add(chunk)
    db.commit()
    db.refresh(chunk)
    return chunk
