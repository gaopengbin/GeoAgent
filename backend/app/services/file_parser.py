"""文件解析器：将上传文件转换为 GeoJSON FeatureCollection

支持格式：
- .geojson / .json → 直接加载
- .csv / .xlsx / .xls → 自动识别经纬度列 → Point FeatureCollection
- .kml / .kmz → fiona/fastkml 解析
- .gpx → gpxpy 解析
- .zip (Shapefile) → fiona/geopandas 解析
"""

import io
import json
import logging
import os
import zipfile
from typing import Optional

logger = logging.getLogger(__name__)

# 常见经纬度列名
LON_NAMES = {"lng", "lon", "longitude", "x", "经度", "long"}
LAT_NAMES = {"lat", "latitude", "y", "纬度"}


def parse_file(file_path: str, crs: str = "EPSG:4326") -> dict:
    """解析文件为 GeoJSON FeatureCollection

    Args:
        file_path: 文件绝对路径
        crs: 原始坐标系

    Returns:
        GeoJSON FeatureCollection dict

    Raises:
        ValueError: 不支持的格式或解析失败
    """
    ext = os.path.splitext(file_path)[1].lower()

    if ext in (".geojson", ".json"):
        return _parse_geojson(file_path)
    elif ext == ".csv":
        return _parse_csv(file_path)
    elif ext in (".xlsx", ".xls"):
        return _parse_excel(file_path)
    elif ext == ".kml":
        return _parse_kml(file_path)
    elif ext == ".kmz":
        return _parse_kmz(file_path)
    elif ext == ".gpx":
        return _parse_gpx(file_path)
    elif ext == ".zip":
        return _parse_shapefile_zip(file_path)
    else:
        raise ValueError(f"不支持的文件格式: {ext}")


def _parse_geojson(file_path: str) -> dict:
    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except UnicodeDecodeError:
        import chardet
        with open(file_path, "rb") as f:
            raw = f.read()
        detected = chardet.detect(raw)
        encoding = detected.get("encoding", "utf-8")
        data = json.loads(raw.decode(encoding))
    if data.get("type") == "FeatureCollection":
        return data
    elif data.get("type") == "Feature":
        return {"type": "FeatureCollection", "features": [data]}
    elif data.get("type") in ("Point", "LineString", "Polygon", "MultiPoint", "MultiLineString", "MultiPolygon"):
        return {"type": "FeatureCollection", "features": [{"type": "Feature", "geometry": data, "properties": {}}]}
    elif data.get("type") == "GeometryCollection":
        features = [
            {"type": "Feature", "geometry": geom, "properties": {"index": i}}
            for i, geom in enumerate(data.get("geometries", []))
        ]
        return {"type": "FeatureCollection", "features": features}
    raise ValueError("JSON 文件不是有效的 GeoJSON 格式")


def _parse_csv(file_path: str) -> dict:
    import csv
    with open(file_path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return _rows_to_geojson(rows)


def _parse_excel(file_path: str) -> dict:
    import openpyxl
    wb = openpyxl.load_workbook(file_path, read_only=True, data_only=True)
    ws = wb.active
    rows_iter = ws.iter_rows(values_only=True)
    headers = [str(h).strip() if h else f"col_{i}" for i, h in enumerate(next(rows_iter))]
    rows = [dict(zip(headers, row)) for row in rows_iter]
    wb.close()
    return _rows_to_geojson(rows)


def _rows_to_geojson(rows: list[dict]) -> dict:
    """表格行 → GeoJSON（自动识别经纬度列）"""
    if not rows:
        raise ValueError("文件为空")

    headers_lower = {k.lower().strip(): k for k in rows[0].keys()}
    lon_col = next((headers_lower[n] for n in LON_NAMES if n in headers_lower), None)
    lat_col = next((headers_lower[n] for n in LAT_NAMES if n in headers_lower), None)

    if not lon_col or not lat_col:
        raise ValueError(
            f"无法识别经纬度列。列名: {list(rows[0].keys())}。"
            f"请确保包含 longitude/latitude 或 lng/lat 或 经度/纬度 列。"
        )

    features = []
    for row in rows:
        try:
            lon = float(row[lon_col])
            lat = float(row[lat_col])
        except (ValueError, TypeError):
            continue
        props = {k: v for k, v in row.items() if k not in (lon_col, lat_col)}
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": props,
        })

    if not features:
        raise ValueError("未能从表格中提取有效坐标点")

    return {"type": "FeatureCollection", "features": features}


def _parse_kml(file_path: str) -> dict:
    try:
        import geopandas as gpd
        gdf = gpd.read_file(file_path, driver="KML")
        return json.loads(gdf.to_json())
    except Exception as e:
        logger.warning("geopandas KML 解析失败: %s，尝试 fastkml", e)
        return _parse_kml_fastkml(file_path)


def _parse_kml_fastkml(file_path: str) -> dict:
    from fastkml import kml as fastkml
    with open(file_path, "rb") as f:
        k = fastkml.KML()
        k.from_string(f.read())

    features = []
    for doc in k.features():
        for folder in doc.features():
            for pm in folder.features():
                if pm.geometry:
                    features.append({
                        "type": "Feature",
                        "geometry": json.loads(pm.geometry.json),
                        "properties": {"name": pm.name or "", "description": pm.description or ""},
                    })
    return {"type": "FeatureCollection", "features": features}


def _parse_kmz(file_path: str) -> dict:
    with zipfile.ZipFile(file_path, "r") as zf:
        kml_names = [n for n in zf.namelist() if n.endswith(".kml")]
        if not kml_names:
            raise ValueError("KMZ 中未找到 .kml 文件")
        with zf.open(kml_names[0]) as kml_file:
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".kml", delete=False) as tmp:
                tmp.write(kml_file.read())
                tmp_path = tmp.name
    try:
        return _parse_kml(tmp_path)
    finally:
        os.unlink(tmp_path)


def _parse_gpx(file_path: str) -> dict:
    try:
        import geopandas as gpd
        gdf = gpd.read_file(file_path, layer="waypoints")
        return json.loads(gdf.to_json())
    except Exception:
        pass

    import gpxpy
    with open(file_path, "r", encoding="utf-8") as f:
        gpx = gpxpy.parse(f)

    features = []
    for wp in gpx.waypoints:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [wp.longitude, wp.latitude, wp.elevation or 0]},
            "properties": {"name": wp.name or "", "description": wp.description or ""},
        })
    for track in gpx.tracks:
        for segment in track.segments:
            coords = [[p.longitude, p.latitude, p.elevation or 0] for p in segment.points]
            if coords:
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "LineString", "coordinates": coords},
                    "properties": {"name": track.name or ""},
                })

    return {"type": "FeatureCollection", "features": features}


def _parse_shapefile_zip(file_path: str) -> dict:
    import geopandas as gpd
    gdf = gpd.read_file(f"zip://{file_path}")
    return json.loads(gdf.to_json())
