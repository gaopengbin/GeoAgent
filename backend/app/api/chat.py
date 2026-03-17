import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.schemas import ChatRequest
from app.models.tables import Session, Message
from app.agent.geo_agent import run_agent_stream
from app.services.llm import get_llm

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


@router.post("/chat")
async def chat(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    session_id = req.session_id or str(uuid.uuid4())

    # 确保 session 存在
    session = await db.get(Session, session_id)
    if not session:
        session = Session(id=session_id, title=req.message[:50])
        db.add(session)

    # 保存用户消息
    user_msg = Message(
        session_id=session_id,
        role="user",
        content=req.message,
    )
    db.add(user_msg)
    await db.commit()

    # 加载历史消息（不含刚刚保存的当前用户消息，最多取最近 20 条）
    history_rows = (
        await db.execute(
            select(Message.role, Message.content)
            .where(Message.session_id == session_id, Message.id != user_msg.id)
            .order_by(Message.created_at)
            .limit(20)
        )
    ).all()
    history = [{"role": r.role, "content": r.content} for r in history_rows]

    # 提取用户选项
    model_override = None
    temperature = 0.3
    api_key_override = None
    base_url_override = None
    locale = "zh-CN"
    if req.options:
        model_override = req.options.model
        temperature = req.options.temperature
        api_key_override = req.options.api_key
        base_url_override = req.options.base_url
        locale = req.options.locale or "zh-CN"

    async def event_stream():
        # SSE: session
        yield _sse("session", {"session_id": session_id})

        full_reply = ""
        collected_tool_calls: list[dict] = []

        try:
            async for event in run_agent_stream(
                session_id=session_id,
                user_message=req.message,
                history=history,
                model_override=model_override,
                temperature=temperature,
                api_key_override=api_key_override,
                base_url_override=base_url_override,
                locale=locale,
            ):
                event_type = event.get("type", "text")

                if event_type == "text":
                    full_reply += event.get("content", "")
                    yield _sse("text", event)

                elif event_type == "tool_call":
                    collected_tool_calls.append({
                        "name": event.get("tool_name", ""),
                        "args": event.get("tool_args"),
                        "status": "running",
                        "statusText": event.get("description", ""),
                    })
                    yield _sse("tool_call", event)

                elif event_type == "tool_result":
                    # 回填对应 tool_call 的结果
                    tn = event.get("tool_name", "")
                    for tc in reversed(collected_tool_calls):
                        if tc["name"] == tn and tc["status"] == "running":
                            tc["status"] = "done" if event.get("success") else "error"
                            tc["statusText"] = event.get("summary", "")
                            tc["result"] = event.get("result")
                            tc["dataRefId"] = event.get("data_ref_id")
                            break
                    yield _sse("tool_result", event)

                elif event_type == "map_command":
                    yield _sse("map_command", event)

                elif event_type == "chart_option":
                    yield _sse("chart_option", event)

                elif event_type == "thinking":
                    yield _sse("thinking", event)

                elif event_type == "report":
                    yield _sse("report", event)

                elif event_type == "error":
                    yield _sse("error", event)

                elif event_type == "done":
                    yield _sse("done", event)

        except Exception as e:
            logger.exception("Agent 执行异常")
            yield _sse("error", {"message": str(e)})
            yield _sse("done", {"session_id": session_id})

        # 保存 assistant 消息
        if full_reply or collected_tool_calls:
            assistant_msg = Message(
                session_id=session_id,
                role="assistant",
                content=full_reply,
                tool_calls=collected_tool_calls if collected_tool_calls else None,
            )
            db.add(assistant_msg)
            session.updated_at = datetime.now(timezone.utc)
            await db.commit()

            # 新会话自动生成标题
            if not history:
                try:
                    title = await _generate_title(req.message, full_reply[:200], locale)
                    session.title = title
                    await db.commit()
                    yield _sse("title", {"session_id": session_id, "title": title})
                except Exception:
                    logger.debug("标题生成失败，保留默认标题")

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


async def _generate_title(user_message: str, ai_reply: str, locale: str = "zh-CN") -> str:
    """用 fast LLM 为新会话生成简洁标题"""
    llm = get_llm(tier="fast", temperature=0.3)
    if locale == "en":
        prompt = (
            f"Generate a concise title (max 15 words, no quotes) for this conversation:\n"
            f"User: {user_message[:100]}\n"
            f"Assistant: {ai_reply[:150]}"
        )
    else:
        prompt = (
            f"请为以下对话生成一个简洁的中文标题（不超过15个字，不要引号）：\n"
            f"用户：{user_message[:100]}\n"
            f"助手：{ai_reply[:150]}"
        )
    resp = await llm.ainvoke(prompt)
    title = resp.content.strip().strip('"\'""''')
    return title[:30] if title else user_message[:50]


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
