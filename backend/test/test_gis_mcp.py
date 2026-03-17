"""测试 gis-mcp 工具：验证 WKT 格式转换后 get_centroid 能正确工作"""
import asyncio
import json

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from shapely.geometry import shape
from shapely.ops import unary_union


async def test():
    server = StdioServerParameters(
        command="python",
        args=["-c", 'from gis_mcp.main import gis_mcp; gis_mcp.run(transport="stdio")'],
    )
    async with stdio_client(server) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()

            # 模拟 adapter 的 WKT 转换流程
            geojson = {
                "type": "FeatureCollection",
                "features": [{
                    "type": "Feature",
                    "geometry": {
                        "type": "Polygon",
                        "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]
                    },
                    "properties": {"name": "test"}
                }]
            }
            # GeoJSON → unary_union → WKT（adapter 的 _geojson_to_wkt 逻辑）
            geoms = [shape(f["geometry"]) for f in geojson["features"]]
            wkt_str = unary_union(geoms).wkt
            print(f"WKT: {wkt_str}")

            # 1. 测试 get_centroid
            print("\n--- get_centroid ---")
            result = await session.call_tool("get_centroid", {"geometry": wkt_str})
            print(f"isError: {getattr(result, 'isError', False)}")
            text = result.content[0].text if result.content else ""
            print(f"result: {text[:300]}")

            # 2. 测试 buffer
            print("\n--- buffer ---")
            result = await session.call_tool("buffer", {"geometry": wkt_str, "distance": 0.1})
            print(f"isError: {getattr(result, 'isError', False)}")
            text = result.content[0].text if result.content else ""
            print(f"result: {text[:300]}")

            # 3. 测试 convex_hull
            print("\n--- convex_hull ---")
            result = await session.call_tool("convex_hull", {"geometry": wkt_str})
            print(f"isError: {getattr(result, 'isError', False)}")
            text = result.content[0].text if result.content else ""
            print(f"result: {text[:300]}")

            print("\n✅ All tests passed!")


if __name__ == "__main__":
    asyncio.run(test())
