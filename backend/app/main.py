import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import init_db
from app.api.chat import router as chat_router
from app.api.data import router as data_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    await init_db()
    logging.getLogger(__name__).info("GeoAgent backend started")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    description="AI-driven geospatial analysis platform — Talk to your map.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(data_router, prefix="/api")

logger = logging.getLogger(__name__)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    ms = (time.time() - start) * 1000
    if not request.url.path.startswith("/api/health"):
        logger.info("%s %s %.0fms %d", request.method, request.url.path, ms, response.status_code)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}


def _get_available_models() -> list[dict]:
    """基于 config.py 实际配置动态生成可用模型列表"""
    seen = set()
    models = []
    for model_name, label, is_default in [
        (settings.LLM_MODEL, "主力模型", True),
        (settings.LLM_FAST_MODEL, "快速模型", False),
        (settings.LLM_ENHANCED_MODEL, "增强模型", False),
        (settings.LLM_REASONING_MODEL, "推理模型", False),
    ]:
        if model_name and model_name not in seen:
            seen.add(model_name)
            models.append({"id": model_name, "name": f"{model_name} ({label})", "default": is_default})
    return models


@app.get("/api/config")
async def get_config():
    return {
        "cesium_token": settings.CESIUM_TOKEN,
        "tianditu_token": settings.TIANDITU_TOKEN,
        "max_upload_size": settings.MAX_UPLOAD_SIZE,
        "supported_formats": [
            ".geojson", ".json", ".csv", ".xlsx", ".xls",
            ".kml", ".kmz", ".gpx", ".zip",
        ],
        "available_models": _get_available_models(),
        "available_basemaps": [
            {"id": "dark", "name": "暗色", "color": "#1a1a2e"},
            {"id": "satellite", "name": "卫星", "color": "#2d5a27"},
            {"id": "standard", "name": "标准", "color": "#e8e4d8"},
        ],
        "amap_available": bool(settings.AMAP_API_KEY),
        "cesium_runtime_ws_url": settings.CESIUM_RUNTIME_URL.replace("http://", "ws://").replace("https://", "wss://"),
    }
