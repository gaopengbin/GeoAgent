"""
cesium-mcp-runtime HTTP client

向 cesium-mcp-runtime 推送地图命令（POST /api/command），
替代原先通过 SSE 传输 map_command 的方式。
"""

import logging
from typing import List, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None


def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(timeout=5.0)
    return _client


async def push_map_commands(
    commands: List[dict],
    session_id: str = "default",
) -> bool:
    if not commands:
        return True

    url = f"{settings.CESIUM_RUNTIME_URL}/api/command"
    payload = {
        "sessionId": session_id,
        "commands": commands,
    }

    try:
        resp = await _get_client().post(url, json=payload)
        if resp.status_code == 200:
            data = resp.json()
            sent = data.get("sent", 0)
            logger.debug("[runtime] pushed %d/%d commands", sent, len(commands))
            if sent == 0:
                logger.debug("[runtime] sent=0 (no browser connected), falling back to SSE")
                return False
            return True
        else:
            logger.warning("[runtime] HTTP %d: %s", resp.status_code, resp.text[:200])
            return False
    except httpx.ConnectError:
        logger.debug("[runtime] cesium-mcp-runtime not reachable at %s", url)
        return False
    except Exception as e:
        logger.warning("[runtime] push failed: %s", e)
        return False
