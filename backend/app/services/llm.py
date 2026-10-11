"""LLM 调用封装：OpenAI 兼容接口（DashScope 等），支持流式/非流式与 JSON 提取"""
import json
import time
from typing import Generator

from openai import OpenAI
from sqlalchemy.orm import Session

from ..models import AiConfig, PromptTemplate


class LlmError(Exception):
    pass


def get_active_config(db: Session, config_id: int | None = None) -> AiConfig:
    """取可用的模型配置：指定 id 时必须是启用配置，否则取最新的启用配置"""
    q = db.query(AiConfig).filter(AiConfig.is_enabled == True)  # noqa: E712
    if config_id:
        cfg = q.filter(AiConfig.id == config_id).first()
        if not cfg:
            raise LlmError("所选 AI 模型配置不存在或未启用，请重新选择")
    else:
        cfg = q.order_by(AiConfig.id.desc()).first()
    if not cfg or not cfg.api_key:
        raise LlmError("未配置启用的 AI 模型，请先在管理后台「AI 模型配置」中启用")
    return cfg


def get_prompt(db: Session, scene: str, prompt_id: int | None = None) -> PromptTemplate:
    """取场景模板：指定 id 时必须是启用模板，否则取该场景第一个启用模板"""
    q = db.query(PromptTemplate).filter(PromptTemplate.scene == scene, PromptTemplate.status == True)  # noqa: E712
    if prompt_id:
        tpl = q.filter(PromptTemplate.id == prompt_id).first()
        if not tpl:
            raise LlmError("所选 Prompt 模板不存在或未启用，请重新选择")
    else:
        tpl = q.order_by(PromptTemplate.id.asc()).first()
    if not tpl:
        raise LlmError(f"场景 {scene} 下没有启用的 Prompt 模板，请检查 Prompt 模板管理")
    return tpl


def render_prompt(template: str, **variables: str) -> str:
    text = template
    for key, value in variables.items():
        text = text.replace("{" + key + "}", value or "（未填写）")
    return text


def build_messages(prompt: str, resume_text: str, target_position: str, job_desc: str) -> list:
    user_content = render_prompt(
        prompt,
        resume_text=resume_text,
        target_position=target_position,
        job_desc=job_desc,
    )
    return [
        {"role": "system", "content": "你是一位专业的简历优化与求职辅导专家，回答严谨、具体、可执行。"},
        {"role": "user", "content": user_content},
    ]


def chat_once(cfg: AiConfig, messages: list, temperature: float = 0.6) -> str:
    """非流式调用，返回完整文本"""
    try:
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=120)
        resp = client.chat.completions.create(
            model=cfg.model_name,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""
    except LlmError:
        raise
    except Exception as e:
        raise LlmError(f"模型调用失败：{e}")


def iter_stream(cfg: AiConfig, messages: list, temperature: float = 0.6) -> Generator[str, None, None]:
    """流式调用，逐段 yield 文本增量"""
    try:
        client = OpenAI(api_key=cfg.api_key, base_url=cfg.base_url, timeout=180)
        stream = client.chat.completions.create(
            model=cfg.model_name,
            messages=messages,
            temperature=temperature,
            stream=True,
        )
        for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            piece = getattr(delta, "content", None)
            if piece:
                yield piece
    except LlmError:
        raise
    except Exception as e:
        raise LlmError(f"模型流式调用失败：{e}")


def extract_json(text: str) -> dict:
    """从模型输出中稳健地提取第一个 JSON 对象"""
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    start = text.find("{")
    if start == -1:
        raise LlmError("模型未返回 JSON 结构化结果")
    decoder = json.JSONDecoder()
    try:
        obj, _ = decoder.raw_decode(text[start:])
        return obj
    except json.JSONDecodeError:
        raise LlmError("模型返回的 JSON 解析失败，请重试")


def elapsed_ms(start: float) -> int:
    return int((time.time() - start) * 1000)
