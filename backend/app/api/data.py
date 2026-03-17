import csv
import io
import json
import os
import uuid
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.schemas import UploadResponse
from app.models.tables import UploadedFile, Session, Message

router = APIRouter(tags=["data"])

ALLOWED_EXTENSIONS = {
    ".geojson", ".json", ".csv", ".xlsx", ".xls",
    ".kml", ".kmz", ".gpx", ".zip",
}


@router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    session_id: str = Form(None),
    crs: str = Form("EPSG:4326"),
    db: AsyncSession = Depends(get_db),
):
    # 校验扩展名
    ext = _get_extension(file.filename)
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(400, f"不支持的文件格式: {ext}，允许: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    # 校验大小
    content = await file.read()
    if len(content) > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(413, f"文件过大，最大允许 {settings.MAX_UPLOAD_SIZE // (1024*1024)}MB")

    # 确保 session
    if not session_id:
        session_id = str(uuid.uuid4())
    session = await db.get(Session, session_id)
    if not session:
        session = Session(id=session_id)
        db.add(session)

    # 保存文件
    file_id = str(uuid.uuid4())
    session_dir = os.path.join(settings.UPLOAD_DIR, session_id)
    os.makedirs(session_dir, exist_ok=True)
    file_path = os.path.join(session_dir, f"{file_id}{ext}")
    with open(file_path, "wb") as f:
        f.write(content)

    # 解析文件并注册到 SessionDataContext
    import logging
    from app.services.file_parser import parse_file
    from app.services.session_context import get_session_context

    _logger = logging.getLogger(__name__)

    feature_count = 0
    geometry_type = None
    bbox = None
    properties: list[str] = []
    data_ref_id = None

    try:
        geojson = parse_file(file_path, crs=crs)
        features = geojson.get("features", [])
        feature_count = len(features)
        if features:
            geometry_type = features[0].get("geometry", {}).get("type")
            props = features[0].get("properties", {})
            properties = list(props.keys()) if props else []

        ctx = get_session_context(session_id)
        data_ref_id = ctx.register(geojson, source=f"upload:{file.filename}")
        _logger.info("文件 %s 已解析并注册为 %s（%d 个要素）", file.filename, data_ref_id, feature_count)
    except Exception as e:
        _logger.warning("文件解析失败（将仅保存原始文件）: %s", e)

    record = UploadedFile(
        id=file_id,
        session_id=session_id,
        filename=file.filename,
        file_type=ext.lstrip("."),
        file_size=len(content),
        file_path=file_path,
        feature_count=feature_count,
        geometry_type=geometry_type,
        crs=crs,
    )
    db.add(record)
    await db.commit()

    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        type=ext.lstrip("."),
        size=len(content),
        feature_count=feature_count,
        geometry_type=geometry_type,
        crs=crs,
        properties=properties,
        data_ref_id=data_ref_id,
    )


@router.post("/register_geojson")
async def register_geojson(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """接收前端绘制的 GeoJSON，注册到 SessionDataContext 并返回 data_ref_id"""
    import logging
    from app.services.session_context import get_session_context

    _logger = logging.getLogger(__name__)

    session_id = payload.get("session_id")
    geojson = payload.get("geojson")
    source = payload.get("source", "draw")

    if not session_id or not geojson:
        raise HTTPException(400, "缺少 session_id 或 geojson")

    features = geojson.get("features", [])
    feature_count = len(features)
    geometry_type = None
    if features:
        geometry_type = features[0].get("geometry", {}).get("type")

    ctx = get_session_context(session_id)
    data_ref_id = ctx.register(geojson, source=source)
    _logger.info("绘制数据已注册为 %s（%d 个要素）", data_ref_id, feature_count)

    return {
        "data_ref_id": data_ref_id,
        "feature_count": feature_count,
        "geometry_type": geometry_type,
    }


@router.get("/sessions")
async def list_sessions(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    result = await db.execute(select(Session).order_by(Session.updated_at.desc()))
    sessions = result.scalars().all()
    return [
        {
            "id": s.id,
            "title": s.title,
            "created_at": s.created_at.isoformat(),
            "updated_at": s.updated_at.isoformat(),
        }
        for s in sessions
    ]


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    from sqlalchemy import select
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()
    return {
        "id": session.id,
        "title": session.title,
        "messages": [
            {
                "id": m.id,
                "role": m.role,
                "content": m.content,
                "map_commands": m.map_commands,
                "tool_calls": m.tool_calls,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
    }


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str, db: AsyncSession = Depends(get_db)):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    await db.delete(session)
    await db.commit()

    from app.services.session_context import remove_session_context
    from app.services.gis_adapter import cleanup_gis_adapter
    remove_session_context(session_id)
    await cleanup_gis_adapter(session_id)

    return {"status": "deleted"}


@router.get("/layers/{session_id}")
async def get_layers(session_id: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import select
    from app.models.tables import Layer
    result = await db.execute(
        select(Layer).where(Layer.session_id == session_id).order_by(Layer.created_at)
    )
    layers = result.scalars().all()
    return [
        {
            "id": l.id,
            "name": l.name,
            "layer_type": l.layer_type,
            "visible": l.visible,
            "style": l.style,
            "data_ref_id": l.data_ref_id,
            "feature_count": l.feature_count,
            "created_at": l.created_at.isoformat(),
        }
        for l in layers
    ]


@router.get("/sessions/{session_id}/export")
async def export_session(
    session_id: str,
    format: str = Query("markdown", regex="^(markdown|json)$"),
    db: AsyncSession = Depends(get_db),
):
    """导出会话为 Markdown 或 JSON"""
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "会话不存在")
    from sqlalchemy import select
    result = await db.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at)
    )
    messages = result.scalars().all()

    if format == "json":
        data = {
            "session_id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "messages": [
                {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
                for m in messages
            ],
        }
        content = json.dumps(data, ensure_ascii=False, indent=2)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(f'{session.title or session_id}.json')}"},
        )

    # Markdown
    lines = [f"# {session.title or '对话记录'}\n"]
    for m in messages:
        prefix = "**用户**" if m.role == "user" else "**AI**"
        lines.append(f"{prefix}：\n\n{m.content}\n\n---\n")
    content = "\n".join(lines)
    return Response(
        content=content,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(f'{session.title or session_id}.md')}"},
    )


@router.get("/data/{ref_id}/export")
async def export_data(
    ref_id: str,
    format: str = Query("geojson", regex="^(geojson|csv)$"),
):
    """导出 data_ref 数据为 GeoJSON 或 CSV"""
    from app.services.session_context import _contexts, get_session_context, REFS_DIR

    geojson = None
    for ctx in _contexts.values():
        data = ctx.get(ref_id)
        if data:
            geojson = data
            break

    if not geojson and os.path.isdir(REFS_DIR):
        for session_dir in os.listdir(REFS_DIR):
            data_path = os.path.join(REFS_DIR, session_dir, f"{ref_id}.json")
            if os.path.exists(data_path):
                ctx = get_session_context(session_dir)
                data = ctx.get(ref_id)
                if data:
                    geojson = data
                    break

    if not geojson:
        raise HTTPException(404, f"数据引用 {ref_id} 不存在或已过期")

    if format == "geojson":
        content = json.dumps(geojson, ensure_ascii=False, indent=2)
        return Response(
            content=content,
            media_type="application/geo+json",
            headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(f'{ref_id}.geojson')}"},
        )

    # CSV
    features = geojson.get("features", [])
    if not features:
        raise HTTPException(400, "数据中无要素，无法导出 CSV")

    all_keys = set()
    for f in features:
        props = f.get("properties", {})
        if props:
            all_keys.update(props.keys())
    all_keys = sorted(all_keys)

    buf = io.StringIO()
    writer = csv.writer(buf)
    header = ["longitude", "latitude"] + list(all_keys)
    writer.writerow(header)
    for f in features:
        geom = f.get("geometry", {})
        coords = geom.get("coordinates", [])
        lon = coords[0] if len(coords) > 0 and isinstance(coords[0], (int, float)) else ""
        lat = coords[1] if len(coords) > 1 and isinstance(coords[1], (int, float)) else ""
        props = f.get("properties", {})
        row = [lon, lat] + [props.get(k, "") for k in all_keys]
        writer.writerow(row)

    content = buf.getvalue()
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(f'{ref_id}.csv')}"},
    )


def _get_extension(filename: str) -> str:
    if not filename:
        return ""
    name = filename.lower()
    for ext in ALLOWED_EXTENSIONS:
        if name.endswith(ext):
            return ext
    idx = name.rfind(".")
    return name[idx:] if idx >= 0 else ""
