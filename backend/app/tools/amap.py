"""高德地图工具集 — 基于高德 Web 服务 REST API

包含：
- amap_geocoding: 地理编码（地址→坐标）+ 逆地理编码（坐标→地址）
- amap_poi_search: POI 关键词搜索
- amap_around_search: 周边 POI 搜索（坐标+半径）
- amap_route_planning: 路径规划（驾车/步行/骑行/公交）
- amap_weather: 天气查询

需要配置 AMAP_API_KEY 环境变量（高德 Web 服务 Key）
申请地址: https://lbs.amap.com/api/webservice/create-project-and-key
"""

import logging
from typing import Literal, Optional

import httpx
from langchain_core.tools import tool

from app.config import settings
from app.utils.coord import gcj02_to_wgs84, gcj02_to_wgs84_geojson

logger = logging.getLogger(__name__)

AMAP_BASE = "https://restapi.amap.com/v3"


def _check_key() -> str:
    if not settings.AMAP_API_KEY:
        raise ValueError("未配置 AMAP_API_KEY，请在 .env 中设置高德地图 API Key")
    return settings.AMAP_API_KEY


@tool
async def amap_geocoding(
    address: Optional[str] = None,
    longitude: Optional[float] = None,
    latitude: Optional[float] = None,
    city: Optional[str] = None,
) -> dict:
    """高德地理编码/逆地理编码。

    使用场景：
    - 地址→坐标：提供 address 参数（可选 city 缩小范围）
    - 坐标→地址：提供 longitude + latitude 参数

    示例：
    - amap_geocoding(address="北京市朝阳区阜通东大街6号") → 坐标
    - amap_geocoding(longitude=116.481, latitude=39.989) → 地址信息
    """
    key = _check_key()

    async with httpx.AsyncClient(timeout=10) as client:
        if address:
            params = {"key": key, "address": address}
            if city:
                params["city"] = city
            resp = await client.get(f"{AMAP_BASE}/geocode/geo", params=params)
            data = resp.json()
            if data.get("status") != "1" or not data.get("geocodes"):
                return {"error": f"地理编码失败: {data.get('info', '未知错误')}"}
            geo = data["geocodes"][0]
            loc = geo["location"].split(",")
            lng, lat = gcj02_to_wgs84(float(loc[0]), float(loc[1]))
            return {
                "longitude": lng,
                "latitude": lat,
                "formatted_address": geo.get("formatted_address", ""),
                "province": geo.get("province", ""),
                "city": geo.get("city", ""),
                "district": geo.get("district", ""),
                "level": geo.get("level", ""),
            }
        elif longitude is not None and latitude is not None:
            resp = await client.get(f"{AMAP_BASE}/geocode/regeo", params={
                "key": key,
                "location": f"{longitude},{latitude}",
                "extensions": "base",
            })
            data = resp.json()
            if data.get("status") != "1":
                return {"error": f"逆地理编码失败: {data.get('info', '未知错误')}"}
            regeo = data.get("regeocode", {})
            addr = regeo.get("addressComponent", {})
            return {
                "formatted_address": regeo.get("formatted_address", ""),
                "province": addr.get("province", ""),
                "city": addr.get("city", ""),
                "district": addr.get("district", ""),
                "township": addr.get("township", ""),
            }
        else:
            return {"error": "请提供 address 或 longitude+latitude"}


@tool
async def amap_poi_search(
    keywords: str,
    city: Optional[str] = None,
    types: Optional[str] = None,
    page_size: int = 25,
    max_results: int = 200,
) -> dict:
    """高德POI关键词搜索（自动翻页获取全部结果）。

    使用场景：在指定城市搜索POI（餐厅、酒店、景点、医院等）。
    - keywords: 搜索关键词（如"肯德基"、"加油站"）
    - city: 城市名或编码（如"北京"）
    - types: POI类型编码（如"050000"餐饮，可不填）
    - max_results: 最多获取条数（默认200，设0获取全部）

    示例：amap_poi_search("星巴克", city="上海")
    """
    key = _check_key()
    offset = min(page_size, 25)
    base_params: dict = {
        "key": key,
        "keywords": keywords,
        "offset": offset,
        "extensions": "all",
    }
    if city:
        base_params["city"] = city
    if types:
        base_params["types"] = types

    all_pois: list = []
    total_count = 0
    page = 1
    cap = max_results if max_results > 0 else 99999

    async with httpx.AsyncClient(timeout=15) as client:
        while len(all_pois) < cap:
            params = {**base_params, "page": page}
            resp = await client.get(f"{AMAP_BASE}/place/text", params=params)
            data = resp.json()
            if data.get("status") != "1":
                if page == 1:
                    return {"error": f"POI搜索失败: {data.get('info', '未知错误')}"}
                break
            if page == 1:
                total_count = int(data.get("count", 0))
            pois = data.get("pois", [])
            if not pois:
                break
            all_pois.extend(pois)
            if len(pois) < offset:
                break
            page += 1

    features = []
    for poi in all_pois[:cap]:
        loc = poi.get("location", "")
        if not loc or "," not in loc:
            continue
        lon, lat = loc.split(",")
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": {
                "name": poi.get("name", ""),
                "type": poi.get("type", ""),
                "address": poi.get("address", ""),
                "tel": poi.get("tel", ""),
                "rating": poi.get("biz_ext", {}).get("rating", ""),
                "city": poi.get("cityname", ""),
                "district": poi.get("adname", ""),
            },
        })

    geojson = gcj02_to_wgs84_geojson({"type": "FeatureCollection", "features": features})

    from app.tools._context import get_tool_context
    ctx = get_tool_context()
    ref_id = ctx.register(geojson, source=f"amap:poi:{keywords}")
    summary = ctx.summary(ref_id)
    return {
        "data_ref_id": ref_id,
        **summary,
        "total": total_count,
        "fetched": len(features),
        "summary": f"高德搜索到{len(features)}个「{keywords}」（共{total_count}条）",
    }


@tool
async def amap_around_search(
    longitude: float,
    latitude: float,
    keywords: Optional[str] = None,
    types: Optional[str] = None,
    radius: int = 1000,
    page_size: int = 25,
    max_results: int = 200,
) -> dict:
    """高德周边POI搜索（以坐标为圆心，按半径搜索，自动翻页）。

    使用场景：搜索某个位置周边的POI。
    - longitude/latitude: 中心坐标
    - keywords: 搜索关键词（可选）
    - types: POI类型编码（可选）
    - radius: 搜索半径（米，最大50000）
    - max_results: 最多获取条数（默认200，设0获取全部）

    示例：amap_around_search(116.397, 39.908, keywords="餐厅", radius=500)
    """
    key = _check_key()
    offset = min(page_size, 25)
    base_params: dict = {
        "key": key,
        "location": f"{longitude},{latitude}",
        "radius": min(radius, 50000),
        "offset": offset,
        "extensions": "all",
        "sortrule": "distance",
    }
    if keywords:
        base_params["keywords"] = keywords
    if types:
        base_params["types"] = types

    all_pois: list = []
    total_count = 0
    page = 1
    cap = max_results if max_results > 0 else 99999

    async with httpx.AsyncClient(timeout=15) as client:
        while len(all_pois) < cap:
            params = {**base_params, "page": page}
            resp = await client.get(f"{AMAP_BASE}/place/around", params=params)
            data = resp.json()
            if data.get("status") != "1":
                if page == 1:
                    return {"error": f"周边搜索失败: {data.get('info', '未知错误')}"}
                break
            if page == 1:
                total_count = int(data.get("count", 0))
            pois = data.get("pois", [])
            if not pois:
                break
            all_pois.extend(pois)
            if len(pois) < offset:
                break
            page += 1

    features = []
    for poi in all_pois[:cap]:
        loc = poi.get("location", "")
        if not loc or "," not in loc:
            continue
        lon, lat = loc.split(",")
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "properties": {
                "name": poi.get("name", ""),
                "type": poi.get("type", ""),
                "address": poi.get("address", ""),
                "distance": poi.get("distance", ""),
                "tel": poi.get("tel", ""),
                "rating": poi.get("biz_ext", {}).get("rating", ""),
            },
        })

    geojson = gcj02_to_wgs84_geojson({"type": "FeatureCollection", "features": features})

    from app.tools._context import get_tool_context
    ctx = get_tool_context()
    label = keywords or types or "POI"
    ref_id = ctx.register(geojson, source=f"amap:around:{label}")
    summary = ctx.summary(ref_id)
    return {
        "data_ref_id": ref_id,
        **summary,
        "total": total_count,
        "fetched": len(features),
        "summary": f"周边{radius}米内搜索到{len(features)}个「{label}」（共{total_count}条）",
    }


@tool
async def amap_route_planning(
    origin_longitude: float,
    origin_latitude: float,
    dest_longitude: float,
    dest_latitude: float,
    mode: Literal["driving", "walking", "bicycling", "transit"] = "driving",
    city: Optional[str] = None,
) -> dict:
    """高德路径规划。

    使用场景：计算两点之间的路线（驾车/步行/骑行/公交）。
    - origin: 起点坐标
    - dest: 终点坐标
    - mode: driving（驾车）/walking（步行）/bicycling（骑行）/transit（公交）
    - city: 公交模式必填（如"北京"）

    示例：amap_route_planning(116.397, 39.908, 121.473, 31.230, mode="driving")
    """
    key = _check_key()
    origin = f"{origin_longitude},{origin_latitude}"
    dest = f"{dest_longitude},{dest_latitude}"

    async with httpx.AsyncClient(timeout=15) as client:
        if mode == "transit":
            if not city:
                return {"error": "公交模式需要提供 city 参数"}
            resp = await client.get(f"{AMAP_BASE}/direction/transit/integrated", params={
                "key": key, "origin": origin, "destination": dest, "city": city,
            })
        elif mode == "bicycling":
            resp = await client.get("https://restapi.amap.com/v4/direction/bicycling", params={
                "key": key, "origin": origin, "destination": dest,
            })
        else:
            resp = await client.get(f"{AMAP_BASE}/direction/{mode}", params={
                "key": key, "origin": origin, "destination": dest,
            })
        data = resp.json()

    if mode == "bicycling":
        if data.get("errcode") != 0:
            return {"error": f"路径规划失败: {data.get('errmsg', '未知错误')}"}
        paths = data.get("data", {}).get("paths", [])
    else:
        if data.get("status") != "1":
            return {"error": f"路径规划失败: {data.get('info', '未知错误')}"}
        route = data.get("route", {})
        if mode == "transit":
            transits = route.get("transits", [])
            results = []
            for t in transits[:3]:
                results.append({
                    "duration_min": round(int(t.get("duration", 0)) / 60, 1),
                    "walking_distance_m": int(t.get("walking_distance", 0)),
                    "cost": t.get("cost", ""),
                    "segments": len(t.get("segments", [])),
                })
            return {
                "mode": "transit",
                "origin": origin,
                "destination": dest,
                "routes": results,
                "summary": f"公交方案{len(results)}条，最快{results[0]['duration_min']}分钟" if results else "未找到公交路线",
            }
        paths = route.get("paths", [])

    if not paths:
        return {"error": "未找到路线"}

    best = paths[0]
    distance_km = round(int(best.get("distance", 0)) / 1000, 2)
    duration_min = round(int(best.get("duration", 0)) / 60, 1)

    # 解析路线坐标为 GeoJSON LineString
    coords = []
    for step in best.get("steps", []):
        polyline = step.get("polyline", "")
        for pt in polyline.split(";"):
            if "," in pt:
                lon, lat = pt.split(",")
                coords.append([float(lon), float(lat)])

    result = {
        "mode": mode,
        "distance_km": distance_km,
        "duration_min": duration_min,
        "origin": origin,
        "destination": dest,
        "summary": f"{mode}路线：{distance_km}公里，约{duration_min}分钟",
    }

    if coords:
        geojson = gcj02_to_wgs84_geojson({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": coords},
                "properties": {
                    "mode": mode,
                    "distance_km": distance_km,
                    "duration_min": duration_min,
                },
            }],
        })
        from app.tools._context import get_tool_context
        ctx = get_tool_context()
        ref_id = ctx.register(geojson, source=f"amap:route:{mode}")
        result["data_ref_id"] = ref_id

    return result


@tool
async def amap_weather(
    city: str,
    extensions: Literal["base", "all"] = "base",
) -> dict:
    """高德天气查询。

    使用场景：查询指定城市的天气信息。
    - city: 城市名称或 adcode（如"北京"或"110000"）
    - extensions: "base"实况天气，"all"预报天气

    示例：amap_weather("北京") / amap_weather("上海", extensions="all")
    """
    key = _check_key()

    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{AMAP_BASE}/weather/weatherInfo", params={
            "key": key, "city": city, "extensions": extensions,
        })
        data = resp.json()

    if data.get("status") != "1":
        return {"error": f"天气查询失败: {data.get('info', '未知错误')}"}

    lives = data.get("lives", [])
    forecasts = data.get("forecasts", [])

    if lives:
        w = lives[0]
        return {
            "city": w.get("city", city),
            "weather": w.get("weather", ""),
            "temperature": w.get("temperature", ""),
            "wind_direction": w.get("winddirection", ""),
            "wind_power": w.get("windpower", ""),
            "humidity": w.get("humidity", ""),
            "report_time": w.get("reporttime", ""),
            "summary": f"{w.get('city', city)}：{w.get('weather', '')}，{w.get('temperature', '')}°C，湿度{w.get('humidity', '')}%",
        }
    elif forecasts:
        fc = forecasts[0]
        casts = fc.get("casts", [])
        days = []
        for c in casts:
            days.append({
                "date": c.get("date", ""),
                "dayweather": c.get("dayweather", ""),
                "nightweather": c.get("nightweather", ""),
                "daytemp": c.get("daytemp", ""),
                "nighttemp": c.get("nighttemp", ""),
                "daywind": c.get("daywind", ""),
            })
        return {
            "city": fc.get("city", city),
            "forecasts": days,
            "summary": f"{fc.get('city', city)}未来{len(days)}天天气预报",
        }

    return {"error": "未获取到天气数据"}
