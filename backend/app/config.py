from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # App
    APP_NAME: str = "GeoAgent"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:5174,http://localhost:3000"

    # Database（默认 SQLite 方便开发，生产环境用 PostgreSQL）
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/geoagent.db"
    DATABASE_URL_SYNC: str = "sqlite:///./data/geoagent.db"

    # LLM — 主力模型（必填）
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "deepseek-chat"
    LLM_BASE_URL: str = "https://api.deepseek.com/v1"

    # LLM — 快速模型（可选，简单指令用，不配则用主力模型）
    LLM_FAST_MODEL: Optional[str] = None
    LLM_FAST_BASE_URL: Optional[str] = None
    LLM_FAST_API_KEY: Optional[str] = None

    # LLM — 增强模型（可选，复杂多步分析用）
    LLM_ENHANCED_MODEL: Optional[str] = None
    LLM_ENHANCED_BASE_URL: Optional[str] = None
    LLM_ENHANCED_API_KEY: Optional[str] = None

    # LLM — 推理模型（可选，多约束决策用）
    LLM_REASONING_MODEL: Optional[str] = None
    LLM_REASONING_BASE_URL: Optional[str] = None
    LLM_REASONING_API_KEY: Optional[str] = None

    # Cesium
    CESIUM_TOKEN: str = ""
    CESIUM_RUNTIME_URL: str = "http://localhost:9100"

    # 天地图
    TIANDITU_TOKEN: str = ""

    # 高德地图
    AMAP_API_KEY: str = ""

    # Overpass API（OSM 数据查询，可替换为国内可达的镜像）
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"

    # File Upload
    UPLOAD_DIR: str = "data/uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # Session
    SESSION_CACHE_MAX_BYTES: int = 100 * 1024 * 1024  # 100MB per session
    DATA_REF_UPGRADE_THRESHOLD: int = 10 * 1024 * 1024  # 10MB auto upgrade to PostGIS

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


settings = Settings()
