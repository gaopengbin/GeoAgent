"""scene3d 工具组：3D 场景加载

通过 map_command 边信道推送 Cesium 3D 场景指令：
- load_3dtiles: 加载 3D Tiles 模型（建筑、地形、点云等）
- load_terrain: 切换地形服务
- load_imagery_service: 加载 WMS/WMTS/URL 影像服务
"""

from typing import Literal, Optional

from langchain_core.tools import tool


@tool
async def load_3dtiles(
    url: str,
    name: Optional[str] = None,
    max_screen_error: float = 16.0,
    height_offset: float = 0.0,
) -> dict:
    """加载 3D Tiles 数据集到地图（建筑模型、点云、倾斜摄影等）。

    使用场景：当用户说"加载3D建筑"、"显示点云"、"加载倾斜摄影"时使用。
    需要先用 discover_gis_tools("scene3d") 启用此工具。

    示例：load_3dtiles(url="https://example.com/tileset.json", name="城市建筑")
    """
    from app.tools._context import push_map_command

    layer_id = f"3dtiles_{name or 'layer'}_{id(url) & 0xFFFF:04x}"
    push_map_command({
        "action": "load3dTiles",
        "params": {
            "id": layer_id,
            "name": name or "3D Tiles",
            "url": url,
            "maximumScreenSpaceError": max_screen_error,
            "heightOffset": height_offset,
        },
    })
    return {
        "layer_id": layer_id,
        "url": url,
        "summary": f"已发送 3D Tiles 加载指令：{name or url}",
    }


@tool
async def load_terrain(
    provider: Literal["cesiumion", "arcgis", "flat"] = "flat",
    url: Optional[str] = None,
    cesiumion_asset_id: Optional[int] = None,
) -> dict:
    """切换地形服务。

    使用场景：当用户说"开启地形"、"显示山地地形"、"平坦地形"时使用。
    需要先用 discover_gis_tools("scene3d") 启用此工具。

    provider 说明：
    - flat: 平坦地形（默认，无起伏）
    - arcgis: ArcGIS World Elevation（全球30米DEM，免费）
    - cesiumion: Cesium Ion Terrain（需要 asset_id）

    示例：load_terrain(provider="arcgis")
    """
    from app.tools._context import push_map_command

    push_map_command({
        "action": "loadTerrain",
        "params": {
            "provider": provider,
            "url": url,
            "cesiumIonAssetId": cesiumion_asset_id,
        },
    })

    desc = {
        "flat": "平坦地形",
        "arcgis": "ArcGIS 全球地形（30米）",
        "cesiumion": f"Cesium Ion 地形（Asset {cesiumion_asset_id}）",
    }.get(provider, provider)

    return {"provider": provider, "summary": f"地形已切换：{desc}"}


@tool
async def load_imagery_service(
    url: str,
    service_type: Literal["wms", "wmts", "xyz", "arcgis_mapserver"] = "xyz",
    name: Optional[str] = None,
    layer_name: Optional[str] = None,
    opacity: float = 1.0,
) -> dict:
    """加载外部影像服务（WMS/WMTS/XYZ 瓦片/ArcGIS MapServer）。

    使用场景：当用户说"加载卫星影像"、"叠加WMS服务"、"添加影像图层"时使用。
    需要先用 discover_gis_tools("scene3d") 启用此工具。

    示例：
    - 天地图影像：load_imagery_service(url="https://t0.tianditu.gov.cn/img_w/wmts?...", service_type="wmts")
    - XYZ 瓦片：load_imagery_service(url="https://tile.openstreetmap.org/{z}/{x}/{y}.png", service_type="xyz")
    """
    from app.tools._context import push_map_command

    layer_id = f"imagery_{service_type}_{id(url) & 0xFFFF:04x}"
    push_map_command({
        "action": "loadImageryService",
        "params": {
            "id": layer_id,
            "name": name or f"影像服务 ({service_type.upper()})",
            "url": url,
            "serviceType": service_type,
            "layerName": layer_name,
            "opacity": opacity,
        },
    })
    return {
        "layer_id": layer_id,
        "service_type": service_type,
        "summary": f"已发送影像服务加载指令：{name or url[:60]}",
    }
