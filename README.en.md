# GeoAgent — AI-Powered Geospatial Analysis Platform

[中文](./README.md)

> Control maps with natural language. AI handles data ingestion → spatial analysis → visualization → report generation.

## Key Features

- **Natural Language Interaction**: Chat-based map control, no coding required
- **35+ GIS Tools**: Buffer analysis, spatial queries, clustering, kernel density, choropleth, heatmaps, and more
- **Amap (Gaode) Integration**: POI search, nearby search, geocoding, route planning, weather
- **Cesium 3D Globe**: GeoJSON rendering, 3D Tiles, terrain, imagery services, trajectory animation
- **Smart Reports**: Auto-generated Markdown analysis reports with download support
- **Streaming Output**: Real-time SSE push of AI thinking process, tool calls, and map commands
- **Multilingual**: Chinese / English UI with one-click switching; AI responses follow current language
- **Custom LLM**: Configure API Key / Base URL / Model in the frontend; compatible with OpenAI / DeepSeek / Qwen

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vue 3 + TypeScript + Cesium + Pinia + ECharts |
| Backend | Python + FastAPI + LangChain/LangGraph |
| GIS | cesium-mcp + Amap API + GeoPandas + Shapely + PyProj |
| Database | SQLite (dev) / PostGIS (production) |
| Bridge | cesium-mcp-bridge (npm package) |

## Quick Start

### Requirements

- Node.js >= 18
- Python >= 3.11
- LLM API Key (DeepSeek / OpenAI / Qwen)

### 1. Clone

```bash
git clone https://github.com/gaopengbin/GeoAgent.git
cd GeoAgent
```

### 2. Start Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Linux/macOS
# venv\Scripts\activate    # Windows

pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your LLM API Key

python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Start Frontend

```bash
cd frontend
npm install
npm run dev
# Visit http://localhost:5173
```

### 4. Docker (Optional)

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with LLM API Key and Cesium Token

docker-compose up --build
# Frontend: http://localhost:5173  Backend: http://localhost:8000
```

## Multilingual & LLM Configuration

### Language Switching
Click **中文 / EN** buttons in the top-right settings panel to switch UI language. After switching:
- All UI text updates automatically
- AI System Prompt follows the current language
- Language preference is saved in localStorage

### Custom LLM
Configure custom LLM connection in the settings panel:
- **API Key**: Your LLM provider's secret key
- **Base URL**: API base URL (e.g., `https://api.openai.com/v1`)
- **Model Name**: Model name (e.g., `gpt-4o`, `deepseek-chat`)

Click "Apply" after configuration. Subsequent chats will use your custom model. Falls back to the server's `.env` default model when not configured.

## Tool List

| Group | Tools |
|-------|-------|
| Core | geocoding, fetch_osm_data, load_uploaded_file, generate_map_command, generate_report |
| Spatial | buffer_analysis, spatial_query, overlay_analysis, clip_analysis |
| Measurement | distance_calc, area_calc, field_statistics, enrich_geometry_fields |
| Geometry | centroid, convex_hull, simplify_geometry, voronoi |
| Coordinate | transform_crs, get_utm_zone |
| Statistics | spatial_statistics, kernel_density, cluster_analysis |
| Visualization | generate_heatmap, generate_choropleth, generate_chart |
| 3D Scene | load_3dtiles, load_terrain, load_imagery_service |
| Trajectory | play_trajectory |
| Amap | amap_geocoding, amap_poi_search, amap_around_search, amap_route_planning, amap_weather |

## Architecture

```
User → ChatPanel → SSE → FastAPI → LangGraph Agent → Tools
                                        ↓
                              SessionDataContext (sideband)
                                        ↓
                        map_command / chart_option / report
                                        ↓
                   Frontend → CesiumBridge.execute() → Cesium Render
```

Key design decisions:
- **Sideband mechanism**: Large data (GeoJSON) bypasses LLM context via `push_map_command`, sent directly to frontend
- **data_ref_id reference passing**: Tools pass lightweight IDs between steps, avoiding LLM processing of large JSON
- **cesium-mcp-bridge**: Unified Cesium control layer with command dispatch and type-safe calls

## License

MIT
