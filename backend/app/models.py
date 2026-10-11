"""数据库模型：用户、简历、AI模型配置、Prompt模板、AI历史记录"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def now():
    return datetime.now()


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    nickname: Mapped[str] = mapped_column(String(50), default="")
    email: Mapped[str] = mapped_column(String(100), default="")
    phone: Mapped[str] = mapped_column(String(30), default="")
    avatar: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="user")  # user / admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Resume(Base):
    __tablename__ = "resumes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    title: Mapped[str] = mapped_column(String(100))
    target_position: Mapped[str] = mapped_column(String(100), default="")
    job_desc: Mapped[str] = mapped_column(Text, default="")  # 可选：目标岗位JD
    original_text: Mapped[str] = mapped_column(Text, default="")  # 上传解析出的原始文本
    current_text: Mapped[str] = mapped_column(Text, default="")   # 当前优化文本
    file_name: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class AiConfig(Base):
    """AI 模型配置（OpenAI 兼容接口，如阿里云百炼 DashScope）"""
    __tablename__ = "ai_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(50), default="阿里云百炼")
    base_url: Mapped[str] = mapped_column(String(255), default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    api_key: Mapped[str] = mapped_column(String(255), default="")
    model_name: Mapped[str] = mapped_column(String(100), default="qwen-plus")
    is_enabled: Mapped[bool] = mapped_column(default=False)
    remark: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PromptTemplate(Base):
    """Prompt 模板：同一场景可配置多个模板，AI 调用时按需选择"""
    __tablename__ = "prompt_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)  # 如 RESUME_SCORE / RESUME_REWRITE_STAR
    name: Mapped[str] = mapped_column(String(100))
    scene: Mapped[str] = mapped_column(String(20), default="score", index=True)  # score/analysis/suggestion/rewrite/interview
    content: Mapped[str] = mapped_column(Text)  # 支持 {resume_text} {target_position} {job_desc} 占位符
    status: Mapped[bool] = mapped_column(default=True)  # True=启用
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=now, onupdate=now)


class KnowledgeChunk(Base):
    """知识库片段：简历优化领域知识，embedding 后用于 RAG 检索"""
    __tablename__ = "knowledge_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(100))          # 来源标题（UI 展示引用）
    content: Mapped[str] = mapped_column(Text)                # 片段正文
    tag: Mapped[str] = mapped_column(String(30), default="")  # 主题标签
    embedding: Mapped[str] = mapped_column(Text, default="")  # 向量 JSON（懒生成，空=待嵌入）
    enabled: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class AiHistory(Base):
    """AI 调用历史：所有 AI 结果统一落库，用 type 区分场景"""
    __tablename__ = "ai_histories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    resume_id: Mapped[int] = mapped_column(Integer, nullable=True, index=True)
    resume_title: Mapped[str] = mapped_column(String(100), default="")
    prompt_code: Mapped[str] = mapped_column(String(50), default="")
    type: Mapped[str] = mapped_column(String(20), index=True)  # score/analysis/suggestion/rewrite/interview/chat
    model: Mapped[str] = mapped_column(String(100), default="")
    input_text: Mapped[str] = mapped_column(Text, default="")   # 输入摘要（截断保存）
    output_text: Mapped[str] = mapped_column(Text, default="")  # 模型完整输出 / 结构化JSON
    refs: Mapped[str] = mapped_column(Text, default="")         # RAG 检索到的知识库来源 JSON
    score: Mapped[int] = mapped_column(Integer, nullable=True)  # 仅评分场景
    level: Mapped[str] = mapped_column(String(20), default="")  # 仅评分场景
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="success")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
