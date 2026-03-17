"""LLM 多模型连接层：四级模型路由 + OpenAI 兼容接口统一接入"""

from typing import Optional

from langchain_openai import ChatOpenAI

from app.config import settings


def _resolve_api_key(tier_key: Optional[str]) -> str:
    """获取指定层级的 API Key，未配置则降级到主力模型 Key"""
    return tier_key or settings.LLM_API_KEY


def _resolve_base_url(tier_url: Optional[str]) -> str:
    """获取指定层级的 Base URL，未配置则降级到主力模型 URL"""
    return tier_url or settings.LLM_BASE_URL


def get_llm(
    tier: str = "main",
    temperature: float = 0.3,
    user_override: Optional[str] = None,
) -> ChatOpenAI:
    """根据层级获取 LLM 实例

    Args:
        tier: "fast" | "main" | "enhanced" | "reasoning"
        temperature: 采样温度
        user_override: 用户在前端手动选择的模型名，覆盖自动路由

    Returns:
        ChatOpenAI 实例（OpenAI 兼容接口）
    """
    if user_override:
        return ChatOpenAI(
            model=user_override,
            api_key=settings.LLM_API_KEY,
            base_url=settings.LLM_BASE_URL,
            temperature=temperature,
        )

    tier_config = {
        "fast": {
            "model": settings.LLM_FAST_MODEL or settings.LLM_MODEL,
            "base_url": _resolve_base_url(settings.LLM_FAST_BASE_URL),
            "api_key": _resolve_api_key(settings.LLM_FAST_API_KEY),
        },
        "main": {
            "model": settings.LLM_MODEL,
            "base_url": settings.LLM_BASE_URL,
            "api_key": settings.LLM_API_KEY,
        },
        "enhanced": {
            "model": settings.LLM_ENHANCED_MODEL or settings.LLM_MODEL,
            "base_url": _resolve_base_url(settings.LLM_ENHANCED_BASE_URL),
            "api_key": _resolve_api_key(settings.LLM_ENHANCED_API_KEY),
        },
        "reasoning": {
            "model": settings.LLM_REASONING_MODEL or settings.LLM_MODEL,
            "base_url": _resolve_base_url(settings.LLM_REASONING_BASE_URL),
            "api_key": _resolve_api_key(settings.LLM_REASONING_API_KEY),
        },
    }

    cfg = tier_config.get(tier, tier_config["main"])
    return ChatOpenAI(
        model=cfg["model"],
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        temperature=temperature,
    )


def select_model_tier(intent: str, estimated_steps: int) -> str:
    """根据任务复杂度自动选择模型层级"""
    if intent in ("flyTo", "setBasemap", "toggleLayer", "chitchat"):
        return "fast"
    elif estimated_steps > 5 or intent == "multi_step_analysis":
        return "enhanced"
    elif intent in ("site_selection", "comparison", "constraint_optimization"):
        return "reasoning"
    return "main"
