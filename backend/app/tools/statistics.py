"""statistics 工具组：空间统计、核密度、聚类分析

这些工具需要本地 scipy / scikit-learn 计算，不依赖 gis-mcp。
"""

import logging
from typing import Literal, Optional

import numpy as np
from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _extract_coords(geojson: dict) -> np.ndarray:
    """从 GeoJSON FeatureCollection 提取点坐标 [[lon, lat], ...]"""
    coords = []
    for f in geojson.get("features", []):
        geom = f.get("geometry", {})
        gtype = geom.get("type", "")
        if gtype == "Point":
            coords.append(geom["coordinates"][:2])
        elif gtype in ("MultiPoint", "LineString"):
            for c in geom["coordinates"]:
                coords.append(c[:2])
        elif gtype == "Polygon":
            # 用质心近似
            ring = geom["coordinates"][0]
            cx = sum(c[0] for c in ring) / len(ring)
            cy = sum(c[1] for c in ring) / len(ring)
            coords.append([cx, cy])
    return np.array(coords) if coords else np.empty((0, 2))


@tool
async def spatial_statistics(
    data_ref_id: str,
    method: Literal["nearest_neighbor", "mean_center", "standard_distance"] = "nearest_neighbor",
) -> dict:
    """基础空间统计分析。

    使用场景：当用户说"空间分布特征"、"是否聚集"、"平均中心"时使用。
    需要先用 discover_gis_tools("statistics") 启用此工具。

    方法：
    - nearest_neighbor: 最近邻指数（R<1聚集, R=1随机, R>1均匀）
    - mean_center: 平均中心点
    - standard_distance: 标准距离（离散程度）
    """
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    coords = _extract_coords(geojson)
    if len(coords) < 2:
        return {"error": "数据点数不足，至少需要2个点"}

    if method == "mean_center":
        mc = coords.mean(axis=0)
        return {
            "method": "mean_center",
            "longitude": float(mc[0]),
            "latitude": float(mc[1]),
            "point_count": len(coords),
            "summary": f"平均中心: ({mc[0]:.4f}, {mc[1]:.4f})，共{len(coords)}个点",
        }

    elif method == "standard_distance":
        mc = coords.mean(axis=0)
        sd = np.sqrt(np.mean(np.sum((coords - mc) ** 2, axis=1)))
        return {
            "method": "standard_distance",
            "standard_distance_deg": float(sd),
            "standard_distance_km": float(sd * 111.32),
            "mean_center": [float(mc[0]), float(mc[1])],
            "point_count": len(coords),
            "summary": f"标准距离: {sd * 111.32:.2f}km，共{len(coords)}个点",
        }

    else:  # nearest_neighbor
        from scipy.spatial import KDTree
        tree = KDTree(coords)
        dists, _ = tree.query(coords, k=2)
        nn_dists = dists[:, 1]  # 排除自身
        observed_mean = nn_dists.mean()

        n = len(coords)
        bbox = [coords[:, 0].min(), coords[:, 1].min(), coords[:, 0].max(), coords[:, 1].max()]
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        expected_mean = 0.5 / np.sqrt(n / area) if area > 0 else 0

        r_index = observed_mean / expected_mean if expected_mean > 0 else float('inf')
        pattern = "聚集" if r_index < 0.8 else ("均匀" if r_index > 1.2 else "随机")

        return {
            "method": "nearest_neighbor",
            "r_index": float(r_index),
            "observed_mean_distance": float(observed_mean),
            "expected_mean_distance": float(expected_mean),
            "pattern": pattern,
            "point_count": n,
            "summary": f"最近邻指数R={r_index:.3f}，分布模式: {pattern}，共{n}个点",
        }


@tool
async def kernel_density(
    data_ref_id: str,
    bandwidth: Optional[float] = None,
    grid_size: int = 50,
) -> dict:
    """核密度估计（KDE），生成密度网格。

    使用场景：当用户说"热力分析"、"密度分布"、"聚集程度"时使用。

    返回：data_ref_id（密度网格的 GeoJSON 点集）+ 统计摘要
    """
    from scipy.stats import gaussian_kde
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    coords = _extract_coords(geojson)
    if len(coords) < 3:
        return {"error": "数据点数不足，核密度估计至少需要3个点"}

    # KDE
    kde = gaussian_kde(coords.T, bw_method=bandwidth)

    # 生成评估网格
    x_min, y_min = coords.min(axis=0)
    x_max, y_max = coords.max(axis=0)
    x_pad = (x_max - x_min) * 0.1
    y_pad = (y_max - y_min) * 0.1
    xi = np.linspace(x_min - x_pad, x_max + x_pad, grid_size)
    yi = np.linspace(y_min - y_pad, y_max + y_pad, grid_size)
    xx, yy = np.meshgrid(xi, yi)
    positions = np.vstack([xx.ravel(), yy.ravel()])
    density = kde(positions).reshape(xx.shape)

    # 归一化到 0-1
    d_min, d_max = density.min(), density.max()
    if d_max > d_min:
        density_norm = (density - d_min) / (d_max - d_min)
    else:
        density_norm = np.zeros_like(density)

    # 转 GeoJSON 点集（带 density 属性）
    features = []
    for i in range(grid_size):
        for j in range(grid_size):
            if density_norm[i, j] > 0.05:  # 过滤极低密度
                features.append({
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [float(xi[j]), float(yi[i])]},
                    "properties": {"density": float(density_norm[i, j])},
                })

    result_geojson = {"type": "FeatureCollection", "features": features}
    ref_id = ctx.register(result_geojson, source=f"kde:{data_ref_id}")
    summary = ctx.summary(ref_id)

    return {
        "data_ref_id": ref_id,
        **summary,
        "input_points": len(coords),
        "grid_size": grid_size,
        "density_points": len(features),
        "peak_density_location": [float(xi[np.unravel_index(density.argmax(), density.shape)[1]]),
                                   float(yi[np.unravel_index(density.argmax(), density.shape)[0]])],
        "summary": f"核密度分析完成：{len(coords)}个输入点 → {len(features)}个密度网格点",
    }


@tool
async def cluster_analysis(
    data_ref_id: str,
    method: Literal["dbscan", "kmeans"] = "dbscan",
    n_clusters: int = 5,
    eps: float = 0.01,
    min_samples: int = 3,
) -> dict:
    """空间聚类分析。

    使用场景：当用户说"聚类"、"分组"、"DBSCAN"、"K-Means"时使用。

    方法：
    - dbscan: 基于密度的聚类（eps=邻域半径度, min_samples=最小点数）
    - kmeans: K均值聚类（n_clusters=聚类数）

    返回：带 cluster_id 属性的新 data_ref_id
    """
    from sklearn.cluster import DBSCAN, KMeans
    from app.tools._context import get_tool_context

    ctx = get_tool_context()
    geojson = ctx.get(data_ref_id)
    if geojson is None:
        return {"error": f"data_ref_id '{data_ref_id}' 不存在"}

    coords = _extract_coords(geojson)
    if len(coords) < 3:
        return {"error": "数据点数不足，聚类至少需要3个点"}

    features_in = geojson.get("features", [])

    if method == "dbscan":
        model = DBSCAN(eps=eps, min_samples=min_samples)
        labels = model.fit_predict(coords)
    else:
        k = min(n_clusters, len(coords))
        model = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = model.fit_predict(coords)

    # 构建带 cluster_id 的新 GeoJSON
    new_features = []
    for i, feat in enumerate(features_in):
        if i < len(labels):
            new_feat = {**feat}
            new_feat["properties"] = {**feat.get("properties", {}), "cluster_id": int(labels[i])}
            new_features.append(new_feat)

    result_geojson = {"type": "FeatureCollection", "features": new_features}
    ref_id = ctx.register(result_geojson, source=f"cluster:{method}:{data_ref_id}")
    summary_info = ctx.summary(ref_id)

    n_clusters_found = len(set(labels) - {-1})
    n_noise = int(np.sum(labels == -1))

    return {
        "data_ref_id": ref_id,
        **summary_info,
        "method": method,
        "n_clusters": n_clusters_found,
        "n_noise": n_noise,
        "cluster_sizes": {str(k): int(v) for k, v in zip(*np.unique(labels[labels >= 0], return_counts=True))} if n_clusters_found > 0 else {},
        "summary": f"{method}聚类完成：{n_clusters_found}个簇，{n_noise}个噪声点",
    }
