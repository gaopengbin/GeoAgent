"""GCJ-02 ↔ WGS-84 坐标转换

高德地图 API 返回 GCJ-02 坐标，Cesium 使用 WGS-84。
使用迭代法反算，精度约 0.5 米。
"""

import math

_A = 6378245.0
_EE = 0.00669342162296594


def _out_of_china(lng: float, lat: float) -> bool:
    return not (72.004 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)


def _transform_lat(x: float, y: float) -> float:
    ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y * math.pi / 30.0)) * 2.0 / 3.0
    return ret


def _transform_lng(x: float, y: float) -> float:
    ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
    ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
    ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
    ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
    return ret


def gcj02_to_wgs84(lng: float, lat: float) -> tuple[float, float]:
    """GCJ-02 → WGS-84（迭代法，精度 ~0.5m）"""
    if _out_of_china(lng, lat):
        return lng, lat

    dlat = _transform_lat(lng - 105.0, lat - 35.0)
    dlng = _transform_lng(lng - 105.0, lat - 35.0)
    radlat = lat / 180.0 * math.pi
    magic = math.sin(radlat)
    magic = 1 - _EE * magic * magic
    sqrtmagic = math.sqrt(magic)
    dlat = (dlat * 180.0) / ((_A * (1 - _EE)) / (magic * sqrtmagic) * math.pi)
    dlng = (dlng * 180.0) / (_A / sqrtmagic * math.cos(radlat) * math.pi)
    return lng - dlng, lat - dlat


def gcj02_to_wgs84_geojson(geojson: dict) -> dict:
    """将 GeoJSON 中所有坐标从 GCJ-02 转为 WGS-84（原地修改并返回）"""
    if geojson.get("type") == "FeatureCollection":
        for feature in geojson.get("features", []):
            _convert_geometry(feature.get("geometry"))
    elif geojson.get("type") == "Feature":
        _convert_geometry(geojson.get("geometry"))
    elif "coordinates" in geojson:
        _convert_geometry(geojson)
    return geojson


def _convert_geometry(geom: dict | None):
    if not geom or "coordinates" not in geom:
        return
    geom_type = geom.get("type", "")
    coords = geom["coordinates"]

    if geom_type == "Point":
        lng, lat = gcj02_to_wgs84(coords[0], coords[1])
        geom["coordinates"] = [lng, lat] + coords[2:]
    elif geom_type in ("LineString", "MultiPoint"):
        geom["coordinates"] = [_convert_point(p) for p in coords]
    elif geom_type in ("Polygon", "MultiLineString"):
        geom["coordinates"] = [[_convert_point(p) for p in ring] for ring in coords]
    elif geom_type == "MultiPolygon":
        geom["coordinates"] = [
            [[_convert_point(p) for p in ring] for ring in polygon]
            for polygon in coords
        ]


def _convert_point(pt: list) -> list:
    lng, lat = gcj02_to_wgs84(pt[0], pt[1])
    return [lng, lat] + pt[2:]
