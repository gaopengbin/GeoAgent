from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field


# ---------- Chat ----------

class FileAttachment(BaseModel):
    file_id: str
    filename: str


class ChatOptions(BaseModel):
    model: Optional[str] = None
    temperature: float = 0.3
    max_tools: int = 10
    enable_report: bool = True
    api_key: Optional[str] = None
    base_url: Optional[str] = None


class ChatRequest(BaseModel):
    message: str = Field(..., max_length=2000)
    session_id: Optional[str] = None
    attachments: list[FileAttachment] = []
    options: Optional[ChatOptions] = None


# ---------- SSE Events ----------

class ToolCallEvent(BaseModel):
    type: str = "tool_call"
    step: int
    tool_name: str
    tool_args: dict[str, Any] = {}
    description: str


class ToolResultPreview(BaseModel):
    feature_count: Optional[int] = None
    geometry_type: Optional[str] = None
    bbox: Optional[list[float]] = None
    sample_properties: Optional[list[str]] = None


class ToolResultEvent(BaseModel):
    type: str = "tool_result"
    step: int
    tool_name: str
    success: bool
    summary: Optional[str] = None
    data_ref_id: Optional[str] = None
    preview: Optional[ToolResultPreview] = None
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    retry: bool = False


# ---------- Session ----------

class SessionOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    map_commands: Optional[list[dict]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- File Upload ----------

class UploadResponse(BaseModel):
    file_id: str
    filename: str
    type: str
    size: int
    feature_count: int
    geometry_type: Optional[str] = None
    bbox: Optional[list[float]] = None
    crs: str = "EPSG:4326"
    properties: list[str] = []
    data_ref_id: Optional[str] = None
    preview: Optional[dict] = None


# ---------- Layer ----------

class LayerOut(BaseModel):
    id: str
    session_id: str
    name: str
    layer_type: str
    visible: bool = True
    style: Optional[dict] = None
    data_ref_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------- Data Ref Summary ----------

class DataRefSummary(BaseModel):
    data_ref_id: str
    source: str
    feature_count: int
    geometry_type: str
    bbox: list[float]
    properties: list[str]
    storage_level: int = 1
