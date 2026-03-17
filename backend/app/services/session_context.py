import json
import logging
import os
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

from app.config import settings

logger = logging.getLogger(__name__)

REFS_DIR = os.path.join("data", "refs")


@dataclass
class DataRef:
    ref_id: str
    data: dict
    source: str
    created_at: float
    feature_count: int
    geometry_type: str
    bbox: list
    properties: list
    size_bytes: int
    storage_level: int = 1
    postgis_table: Optional[str] = None


class SessionDataContext:

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.data_refs: Dict[str, DataRef] = {}
        self.max_total_bytes = settings.SESSION_CACHE_MAX_BYTES
        self._pending_map_commands: list = []
        self._pending_chart_options: list = []
        self._refs_path = os.path.join(REFS_DIR, session_id)

    def push_map_command(self, cmd: dict):
        self._pending_map_commands.append(cmd)

    def drain_map_commands(self) -> list:
        cmds = self._pending_map_commands[:]
        self._pending_map_commands.clear()
        return cmds

    def push_chart_option(self, option: dict):
        self._pending_chart_options.append(option)

    def drain_chart_options(self) -> list:
        opts = self._pending_chart_options[:]
        self._pending_chart_options.clear()
        return opts

    def register(self, geojson: dict, source: str) -> str:
        safe_source = re.sub(r'[:\\/<>"|?*]', '_', source)
        ref_id = f"ref_{safe_source}_{uuid.uuid4().hex[:8]}"
        features = geojson.get("features", [])
        size = sys.getsizeof(str(geojson))

        ref = DataRef(
            ref_id=ref_id,
            data=geojson,
            source=source,
            created_at=time.time(),
            feature_count=len(features),
            geometry_type=self._detect_geom_type(features),
            bbox=self._calc_bbox(features),
            properties=self._extract_properties(features),
            size_bytes=size,
        )

        if size > settings.DATA_REF_UPGRADE_THRESHOLD:
            self._upgrade_to_postgis(ref)

        self.data_refs[ref_id] = ref
        self._check_total_limit()
        self._persist_ref(ref)
        return ref_id

    def get(self, ref_id: str) -> Optional[dict]:
        ref = self.data_refs.get(ref_id)
        if not ref:
            return None
        if ref.storage_level == 2:
            return self._load_from_disk(ref_id)
        return ref.data

    def summary(self, ref_id: str) -> Optional[dict]:
        ref = self.data_refs.get(ref_id)
        if not ref:
            return None
        return {
            "data_ref_id": ref.ref_id,
            "source": ref.source,
            "feature_count": ref.feature_count,
            "geometry_type": ref.geometry_type,
            "bbox": ref.bbox,
            "properties": ref.properties,
            "storage_level": ref.storage_level,
        }

    def list_refs(self) -> list:
        return [self.summary(rid) for rid in self.data_refs]

    def clear(self):
        self.data_refs.clear()

    # --- 持久化 ---

    def _persist_ref(self, ref: DataRef):
        """将 data_ref 写入磁盘 JSON 文件"""
        os.makedirs(self._refs_path, exist_ok=True)
        file_path = os.path.join(self._refs_path, f"{ref.ref_id}.json")
        meta_path = os.path.join(self._refs_path, f"{ref.ref_id}.meta.json")
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(ref.data, f, ensure_ascii=False)
            meta = {
                "ref_id": ref.ref_id,
                "source": ref.source,
                "created_at": ref.created_at,
                "feature_count": ref.feature_count,
                "geometry_type": ref.geometry_type,
                "bbox": ref.bbox,
                "properties": ref.properties,
                "size_bytes": ref.size_bytes,
            }
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False)
        except Exception as e:
            logger.warning("持久化 data_ref %s 失败: %s", ref.ref_id, e)

    def _load_from_disk(self, ref_id: str) -> Optional[dict]:
        """从磁盘加载 data_ref 的 GeoJSON 数据"""
        file_path = os.path.join(self._refs_path, f"{ref_id}.json")
        if not os.path.exists(file_path):
            return None
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.warning("从磁盘加载 data_ref %s 失败: %s", ref_id, e)
            return None

    def load_persisted_refs(self):
        """从磁盘恢复所有已持久化的 data_refs（会话恢复时调用）"""
        if not os.path.isdir(self._refs_path):
            return
        for fname in os.listdir(self._refs_path):
            if not fname.endswith(".meta.json"):
                continue
            ref_id = fname.replace(".meta.json", "")
            if ref_id in self.data_refs:
                continue
            meta_path = os.path.join(self._refs_path, fname)
            data_path = os.path.join(self._refs_path, f"{ref_id}.json")
            if not os.path.exists(data_path):
                continue
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                with open(data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                ref = DataRef(
                    ref_id=meta["ref_id"],
                    data=data,
                    source=meta["source"],
                    created_at=meta["created_at"],
                    feature_count=meta["feature_count"],
                    geometry_type=meta["geometry_type"],
                    bbox=meta["bbox"],
                    properties=meta["properties"],
                    size_bytes=meta["size_bytes"],
                )
                self.data_refs[ref_id] = ref
            except Exception as e:
                logger.warning("恢复 data_ref %s 失败: %s", ref_id, e)

    # --- internal ---

    @staticmethod
    def _detect_geom_type(features: list) -> str:
        if not features:
            return "Unknown"
        geom = features[0].get("geometry", {})
        return geom.get("type", "Unknown")

    @staticmethod
    def _calc_bbox(features: list) -> list:
        if not features:
            return []
        coords_all = []
        for f in features:
            geom = f.get("geometry", {})
            coords_all.extend(_flatten_coords(geom.get("coordinates", [])))
        if not coords_all:
            return []
        lons = [c[0] for c in coords_all]
        lats = [c[1] for c in coords_all]
        return [min(lons), min(lats), max(lons), max(lats)]

    @staticmethod
    def _extract_properties(features: list) -> list:
        if not features:
            return []
        props = features[0].get("properties", {})
        return list(props.keys()) if props else []

    def _check_total_limit(self):
        total = sum(r.size_bytes for r in self.data_refs.values() if r.storage_level == 1)
        if total <= self.max_total_bytes:
            return
        sorted_refs = sorted(
            [r for r in self.data_refs.values() if r.storage_level == 1],
            key=lambda r: r.created_at,
        )
        for ref in sorted_refs:
            if total <= self.max_total_bytes:
                break
            self._evict_to_disk(ref)
            total -= ref.size_bytes

    def _upgrade_to_postgis(self, ref: DataRef):
        """大数据升级到 PostGIS 存储（MVP阶段仅写磁盘，不实际连接 PostGIS）"""
        logger.info(
            "data_ref %s 大小 %d bytes 超过阈值，降级为磁盘存储（PostGIS 暂未启用）",
            ref.ref_id, ref.size_bytes,
        )
        ref.storage_level = 2

    def _evict_to_disk(self, ref: DataRef):
        """内存超限时释放数据，保留磁盘持久化（已在 register 时写入）"""
        ref.storage_level = 2
        ref.data = {}


# 全局会话上下文管理
_contexts: Dict[str, SessionDataContext] = {}


def get_session_context(session_id: str) -> SessionDataContext:
    if session_id not in _contexts:
        ctx = SessionDataContext(session_id)
        ctx.load_persisted_refs()
        _contexts[session_id] = ctx
    return _contexts[session_id]


def remove_session_context(session_id: str):
    ctx = _contexts.pop(session_id, None)
    if ctx:
        ctx.clear()


def _flatten_coords(coords) -> list:
    if not coords:
        return []
    if isinstance(coords[0], (int, float)):
        return [coords]
    result = []
    for item in coords:
        result.extend(_flatten_coords(item))
    return result
