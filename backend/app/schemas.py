"""Pydantic 请求/响应模型"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------- 认证 / 用户 ----------
class RegisterIn(BaseModel):
    username: str
    password: str
    nickname: str = ""


class LoginIn(BaseModel):
    username: str
    password: str


class ProfileUpdate(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    nickname: str
    email: str
    phone: str
    avatar: str
    role: str
    created_at: datetime


class UserCreateIn(BaseModel):
    username: str
    password: str
    nickname: str = ""
    email: str = ""
    phone: str = ""
    role: str = "user"


class UserUpdateIn(BaseModel):
    nickname: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None  # 管理员重置密码，为空则不修改


class Page(BaseModel):
    total: int
    page: int
    page_size: int
    items: list


# ---------- 简历 ----------
class ResumeCreate(BaseModel):
    title: str
    target_position: str = ""
    job_desc: str = ""
    text: str = ""  # 粘贴的简历文本


class ResumeUpdate(BaseModel):
    title: Optional[str] = None
    target_position: Optional[str] = None
    job_desc: Optional[str] = None
    current_text: Optional[str] = None


class ResumeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    target_position: str
    job_desc: str
    original_text: str
    current_text: str
    file_name: str
    created_at: datetime
    updated_at: datetime


# ---------- AI 模型配置 ----------
class AiConfigIn(BaseModel):
    provider: str = "阿里云百炼"
    base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    api_key: str = ""
    model_name: str = "qwen-plus"
    remark: str = ""


class AiConfigOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    base_url: str
    api_key: str  # 序列化时脱敏
    model_name: str
    is_enabled: bool
    remark: str
    created_at: datetime


# ---------- Prompt 模板 ----------
class PromptCreateIn(BaseModel):
    code: str
    name: str
    scene: str = "score"
    content: str
    status: bool = True


class PromptUpdateIn(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    scene: Optional[str] = None
    content: Optional[str] = None
    status: Optional[bool] = None


class PromptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    scene: str
    content: str
    status: bool
    updated_at: datetime


# ---------- AI ----------
class AiOptionsIn(BaseModel):
    """AI 调用可选参数：指定模型配置与 Prompt 模板（缺省则用默认启用项）"""
    config_id: Optional[int] = None
    prompt_id: Optional[int] = None


class RewriteAdoptIn(BaseModel):
    history_id: int


class HistoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    resume_id: Optional[int]
    resume_title: str
    prompt_code: str
    type: str
    model: str
    input_text: str
    output_text: str
    score: Optional[int]
    level: str
    duration_ms: int
    status: str
    created_at: datetime
