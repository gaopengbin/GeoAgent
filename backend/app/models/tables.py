import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, Boolean, Integer, DateTime, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.config import settings

_USE_POSTGIS = "postgresql" in settings.DATABASE_URL

if _USE_POSTGIS:
    from geoalchemy2 import Geometry as _Geom
    _geom_col = lambda: mapped_column(_Geom("GEOMETRY", srid=4326), nullable=True)
else:
    _geom_col = lambda: mapped_column(Text, nullable=True)


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(200), default="新对话")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    messages: Mapped[list["Message"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    layers: Mapped[list["Layer"]] = relationship(back_populates="session", cascade="all, delete-orphan")
    uploaded_files: Mapped[list["UploadedFile"]] = relationship(back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20))  # user / assistant / system
    content: Mapped[str] = mapped_column(Text, default="")
    map_commands: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    thinking: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship(back_populates="messages")


class Layer(Base):
    __tablename__ = "layers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(200))
    layer_type: Mapped[str] = mapped_column(String(50))  # geojson / heatmap / marker / track
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    style: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_ref_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    geom: Mapped[None] = _geom_col()
    feature_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship(back_populates="layers")


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id", ondelete="CASCADE"))
    filename: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(20))
    file_size: Mapped[int] = mapped_column(Integer)
    file_path: Mapped[str] = mapped_column(String(1000))
    feature_count: Mapped[int] = mapped_column(Integer, default=0)
    geometry_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    bbox: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    crs: Mapped[str] = mapped_column(String(50), default="EPSG:4326")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["Session"] = relationship(back_populates="uploaded_files")
