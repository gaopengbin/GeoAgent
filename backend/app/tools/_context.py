"""工具执行上下文：在 @tool 函数内部访问 SessionDataContext 和 ToolRegistry

使用 contextvars 实现线程安全的上下文传递，由 Agent 运行时在每轮调用前设置。
"""

from contextvars import ContextVar
from typing import Optional

from app.services.session_context import SessionDataContext
from app.tools.registry import ToolRegistry

_current_session_ctx: ContextVar[Optional[SessionDataContext]] = ContextVar(
    "_current_session_ctx", default=None
)
_current_tool_registry: ContextVar[Optional[ToolRegistry]] = ContextVar(
    "_current_tool_registry", default=None
)

def set_tool_context(ctx: SessionDataContext, registry: ToolRegistry):
    """Agent 运行时调用：设置当前工具执行上下文"""
    _current_session_ctx.set(ctx)
    _current_tool_registry.set(registry)


def get_tool_context() -> SessionDataContext:
    """工具内部调用：获取当前 SessionDataContext"""
    ctx = _current_session_ctx.get()
    if ctx is None:
        raise RuntimeError("工具上下文未初始化，请先调用 set_tool_context()")
    return ctx


def push_map_command(cmd: dict):
    """工具内部调用：将 map command 推入边信道（不经过 LLM 上下文）"""
    get_tool_context().push_map_command(cmd)


def push_chart_option(option: dict):
    """工具内部调用：将 ECharts option 推入边信道"""
    get_tool_context().push_chart_option(option)


def get_tool_registry() -> ToolRegistry:
    """工具内部调用：获取当前 ToolRegistry"""
    registry = _current_tool_registry.get()
    if registry is None:
        raise RuntimeError("工具注册表未初始化，请先调用 set_tool_context()")
    return registry
