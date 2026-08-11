import os
import io
import math
import re
import zipfile
import tempfile
import glob
from datetime import datetime

import streamlit as st
import pandas as pd
import numpy as np
from scipy.optimize import least_squares
from pyproj import Transformer
import folium
from streamlit_folium import st_folium
from staticmap import StaticMap, CircleMarker, Line

# ============================================================
# 1. НАСТРОЙКИ И КОНСТАНТЫ
# ============================================================
DEFAULT_FILE = DEFAULT_FILE = "towers.xlsx"
st.set_page_config(
    page_title="Мониторинг лесных пожаров",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed",
)

MAP_TILES = {
    "Гибрид (Google)": {
        "url": "https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}",
        "attr": "Google Maps Hybrid",
    },
    "Спутник (Esri)": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri Satellite",
    },
    "Схема (OpenStreetMap)": {
        "url": "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        "attr": "OpenStreetMap",
    },
    "Рельеф": {
        "url": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
        "attr": "Esri Topo",
    },
    "Тёмная": {
        "url": "https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png",
        "attr": "© OpenStreetMap, © CARTO",
    },
}

# ============================================================
# 2. CSS-ДИЗАЙН (тёмная тема)
# ============================================================
def inject_css():
    st.markdown(
        """
    <style>
    .stApp { background: #0f1419 !important; color: #e6edf3 !important; }
    .block-container { padding-top: 1rem; padding-bottom: 2rem; max-width: 100%; }
    body, .stMarkdown, .stText, p, div, span, label { color: #e6edf3 !important; }
    h1, h2, h3, h4 { color: #ffffff !important; }
    hr { border-color: #30363d !important; }
    .dash-header {
        display: flex; align-items: center; justify-content: space-between;
        padding: 16px 24px;
        background: linear-gradient(135deg, #161b22 0%, #1c2333 100%);
        border: 1px solid #30363d; border-radius: 16px; margin-bottom: 16px;
    }
    .dash-header-title {
        font-size: 1.6rem; font-weight: 700; color: #ffffff;
        display: flex; align-items: center; gap: 12px;
    }
    .dash-header-sub { font-size: 0.9rem; opacity: 0.7; margin-top: 4px; }
    .kpi-card {
        border-radius: 14px; padding: 14px 18px;
        border: 1px solid #30363d;
        background: linear-gradient(135deg, #161b22 0%, #1c2333 100%);
        height: 100%; transition: transform 0.2s, box-shadow 0.2s;
    }
    .kpi-card:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.4); }
    .kpi-label { font-size: 0.8rem; opacity: 0.7; margin-bottom: 6px;
                 text-transform: uppercase; letter-spacing: 0.5px; }
    .kpi-value { font-size: 1.6rem; font-weight: 700; line-height: 1.1; color: #ffffff; }
    .kpi-hint { font-size: 0.75rem; opacity: 0.6; margin-top: 6px; }
    .kpi-ok    { border-left: 4px solid #2e7d32; }
    .kpi-warn  { border-left: 4px solid #f57c00; }
    .kpi-alert { border-left: 4px solid #d32f2f; }
    .status-badge {
        display: inline-flex; align-items: center; gap: 8px;
        padding: 8px 16px; border-radius: 999px;
        font-weight: 600; font-size: 0.9rem;
        border: 1px solid; white-space: nowrap;
    }
    .status-ok      { background: rgba(46,125,50,0.18);  color:#4caf50; border-color:rgba(46,125,50,0.4); }
    .status-warn    { background: rgba(245,124,0,0.18);  color:#ff9800; border-color:rgba(245,124,0,0.4); }
    .status-alert   { background: rgba(211,47,47,0.18);  color:#ef5350; border-color:rgba(211,47,47,0.4); }
    .status-default { background: rgba(128,128,128,0.18); color:#9e9e9e; border-color:rgba(128,128,128,0.4); }
    .map-container {
        border-radius: 16px; overflow: hidden;
        border: 1px solid #30363d;
        box-shadow: 0 4px 20px rgba(0,0,0,0.5);
        background: #0f1419;
    }
    .stTabs [data-baseweb="tab-list"] {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 14px; padding: 6px; gap: 4px;
        box-shadow: inset 0 2px 4px rgba(0,0,0,0.3);
    }
    .stTabs [data-baseweb="tab"] {
        background: transparent !important; color: #8b949e !important;
        border-radius: 10px !important; padding: 10px 18px !important;
        font-weight: 600 !important; font-size: 0.9rem !important;
        border: 1px solid transparent !important;
        transition: all 0.25s ease !important; margin: 0 2px !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(255,255,255,0.05) !important;
        color: #e6edf3 !important;
        border-color: rgba(255,255,255,0.08) !important;
    }
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #1f6feb 0%, #388bfd 100%) !important;
        color: #ffffff !important;
        border-color: rgba(56, 139, 253, 0.5) !important;
        box-shadow: 0 4px 12px rgba(31, 111, 235, 0.35),
                    0 0 0 1px rgba(56, 139, 253, 0.2) !important;
        font-weight: 700 !important;
    }
    .stButton > button {
        background: #1f6feb; color: #ffffff; border: none;
        border-radius: 8px; font-weight: 600; transition: all 0.2s;
    }
    .stButton > button:hover {
        background: #388bfd; transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(31, 111, 235, 0.3);
    }
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > div,
    .stMultiSelect > div > div > div {
        background: #161b22 !important; border: 1px solid #30363d !important;
        color: #e6edf3 !important; border-radius: 8px;
    }
    .stDataFrame { background: #161b22 !important; border-radius: 12px; overflow: hidden; }
    .stAlert { background: #161b22 !important; border: 1px solid #30363d !important; border-radius: 10px !important; }
    ::-webkit-scrollbar { width: 8px; height: 8px; }
    ::-webkit-scrollbar-track { background: #0f1419; }
    ::-webkit-scrollbar-thumb { background: #30363d; border-radius: 4px; }
    ::-webkit-scrollbar-thumb:hover { background: #484f58; }
    .map-legend {
        position: fixed; bottom: 24px; left: 24px; z-index: 1000;
        background: rgba(22, 27, 34, 0.95); color: #e6edf3;
        padding: 12px 14px; border-radius: 12px; font-size: 12px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.4);
        border: 1px solid #30363d; backdrop-filter: blur(8px);
    }
    .map-legend-item { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
    </style>
    """,
        unsafe_allow_html=True,
    )

# ============================================================
# 3. ОБРАБОТКА ДАННЫХ
# ============================================================
def dms_to_decimal(value):
    if pd.isna(value):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 6)
    s = str(value).strip()
    try:
        return round(float(s.replace(",", ".")), 6)
    except Exception:
        pass
    sign = -1 if s.startswith("-") else 1
    match = re.search(r"(\d+)°\s*(\d+)['']?\s*([\d.,]+)", s)
    if not match:
        return None
    degrees = int(match.group(1))
    minutes = int(match.group(2))
    seconds = float(match.group(3).replace(",", "."))
    decimal = degrees + minutes / 60 + seconds / 3600
    return round(sign * decimal, 6)

def read_excel_safe(source):
    try:
        df = pd.read_excel(source, sheet_name=0)
        df.columns = df.columns.str.strip()
        required_cols = ["Лесхоз", "Наименование Вышки", "Широта", "Долгота"]
        missing = [c for c in required_cols if c not in df.columns]
        if missing:
            return None, f"Отсутствуют обязательные столбцы: {missing}"
        df = df.copy()
        df["Наименование Вышки"] = df["Наименование Вышки"].astype(str).str.strip()
        df["Лесхоз"] = df["Лесхоз"].astype(str).str.strip()
        if df["Наименование Вышки"].duplicated().any():
            df["Наименование Вышки"] = (
                df["Наименование Вышки"]
                + "_"
                + df.groupby("Наименование Вышки").cumcount().astype(str)
            )
        df["Широта_dec"] = df["Широта"].apply(dms_to_decimal)
        df["Долгота_dec"] = df["Долгота"].apply(dms_to_decimal)
        df = df.dropna(subset=["Широта_dec", "Долгота_dec"])
        df = df.reset_index(drop=True)
        if len(df) == 0:
            return None, "Не найдено вышек с корректными координатами."
        return df, None
    except Exception as e:
        return None, str(e)

# ============================================================
# 4. МАТЕМАТИКА ТРИАНГУЛЯЦИИ
# ============================================================
class Triangulator:
    def __init__(self, towers_df: pd.DataFrame):
        self.towers = towers_df
        mean_lat = float(towers_df["Широта_dec"].mean())
        mean_lon = float(towers_df["Долгота_dec"].mean())
        zone = int((mean_lon + 180) / 6) + 1
        epsg_code = 32600 + zone if mean_lat >= 0 else 32700 + zone
        self.crs = f"EPSG:{epsg_code}"
        self.proj = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)

    def to_utm(self, lat, lon):
        return self.proj.transform(lon, lat)

    def to_geo(self, x, y):
        lon, lat = self.proj.transform(x, y, direction="INVERSE")
        return lat, lon

    def calc(self, azimuths_dict):
        bearings = []
        for _, row in self.towers.iterrows():
            name = str(row["Наименование Вышки"])
            if name in azimuths_dict:
                x0, y0 = self.to_utm(row["Широта_dec"], row["Долгота_dec"])
                az_rad = math.radians(azimuths_dict[name])
                bearings.append({
                    "x0": x0, "y0": y0,
                    "dx": math.sin(az_rad), "dy": math.cos(az_rad),
                    "azimuth": azimuths_dict[name],
                    "name": name,
                    "lat": row["Широта_dec"], "lon": row["Долгота_dec"],
                })
        if len(bearings) < 2:
            return None

        x0 = float(np.mean([b["x0"] for b in bearings]))
        y0 = float(np.mean([b["y0"] for b in bearings]))

        def residuals(p):
            x, y = p
            res = []
            for b in bearings:
                vx, vy = x - b["x0"], y - b["y0"]
                proj = vx * b["dx"] + vy * b["dy"]
                if proj < 0:
                    res.append(math.hypot(vx, vy))
                else:
                    cx = b["x0"] + proj * b["dx"]
                    cy = b["y0"] + proj * b["dy"]
                    res.append(math.hypot(x - cx, y - cy))
            return np.array(res)

        try:
            result = least_squares(residuals, [x0, y0], method="lm")
        except Exception:
            return None

        rmse = float(np.sqrt(np.mean(result.fun ** 2)))
        if not np.isfinite(rmse):
            return None

        # Расстояние от каждой вышки до точки пересечения (в метрах, UTM)
        fx, fy = result.x
        for b in bearings:
            b["distance"] = math.hypot(fx - b["x0"], fy - b["y0"])

        fire_lat, fire_lon = self.to_geo(*result.x)
        error_radius = rmse * 1.5
        return {
            "lat": fire_lat, "lon": fire_lon,
            "rmse": rmse, "error_radius": error_radius,
            "n_towers": len(bearings), "bearings": bearings,
        }

# ============================================================
# 5. ВИЗУАЛЬНЫЕ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================
def format_distance(meters: float) -> str:
    if meters is None or (isinstance(meters, float) and not np.isfinite(meters)):
        return "—"
    if meters >= 1000:
        return f"{meters / 1000:.2f} км"
    return f"{meters:.0f} м"

def get_accuracy(result: dict):
    if not result:
        return "Нет расчёта", "default"
    good_threshold = float(st.session_state.get("threshold_good", 300.0))
    warn_threshold = float(st.session_state.get("threshold_warn", 1000.0))
    if good_threshold > warn_threshold:
        good_threshold, warn_threshold = warn_threshold, good_threshold
    error_radius = result.get("error_radius", 0)
    n_towers = result.get("n_towers", 0)
    if n_towers >= 3 and error_radius <= good_threshold:
        return "Высокая точность", "ok"
    if n_towers >= 2 and error_radius <= warn_threshold:
        return "Средняя точность", "warn"
    return "Низкая точность", "alert"

def kpi_card(label: str, value: str, hint: str = "", tone: str = "default"):
    tone_class = {
        "default": "", "ok": "kpi-ok", "warn": "kpi-warn", "alert": "kpi-alert"
    }.get(tone, "")
    st.markdown(
        f"""
        <div class="kpi-card {tone_class}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-hint">{hint}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

def get_system_status():
    towers = st.session_state.get("towers")
    result = st.session_state.get("result")
    selected_count = len(st.session_state.get("selected_names", []))
    if towers is None or len(towers) == 0:
        return "Нет данных", "warn"
    if result:
        accuracy_text, tone = get_accuracy(result)
        if tone == "ok":
            return "Очаг рассчитан", "ok"
        if tone == "warn":
            return "Очаг рассчитан: средняя точность", "warn"
        return "Очаг рассчитан: низкая точность", "alert"
    if selected_count < 2:
        return "Выберите минимум 2 вышки", "warn"
    return "Готово к расчёту", "ok"

# ============================================================
# 5а. АВТОМАТИЧЕСКИЙ РАСЧЁТ ЗУМА КАРТЫ
# ============================================================
def calc_map_view(lats, lons, width_px=1400, height_px=720):
    if not lats or not lons:
        return [53.0, 49.0], 9
    if len(lats) == 1:
        return [lats[0], lons[0]], 13

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    lat_pad = max((max_lat - min_lat) * 0.2, 0.02)
    lon_pad = max((max_lon - min_lon) * 0.2, 0.02)
    min_lat, max_lat = min_lat - lat_pad, max_lat + lat_pad
    min_lon, max_lon = min_lon - lon_pad, max_lon + lon_pad

    def merc_y(lat):
        return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))

    y_span = max(merc_y(max_lat) - merc_y(min_lat), 1e-4)
    lon_span = max_lon - min_lon

    zoom_lon = math.log2((width_px / 256) * (360 / lon_span))
    zoom_lat = math.log2((height_px / 256) * (2 * math.pi / y_span))
    zoom = max(4, min(int(min(zoom_lon, zoom_lat)), 15))
    return [(min_lat + max_lat) / 2, (min_lon + max_lon) / 2], zoom

# ============================================================
# 5б. КВАРТАЛЬНАЯ СЕТЬ (SHAPEFILE → GeoJSON)
# ============================================================
def load_quarters_geojson(source, fallback_epsg: int = 4326):
    try:
        import geopandas as gpd
    except ImportError:
        return None, "Не установлен geopandas. Выполните: pip install geopandas"

    try:
        shp_path = source
        if isinstance(source, (bytes, bytearray)) or (
            isinstance(source, str) and source.lower().endswith(".zip")
        ):
            tmp_dir = tempfile.mkdtemp(prefix="quarters_")
            if isinstance(source, (bytes, bytearray)):
                zf = zipfile.ZipFile(io.BytesIO(source))
            else:
                zf = zipfile.ZipFile(source)
            with zf:
                zf.extractall(tmp_dir)
            found = glob.glob(os.path.join(tmp_dir, "**", "*.shp"), recursive=True)
            if not found:
                return None, "В архиве не найден файл .shp"
            shp_path = found[0]

        gdf = gpd.read_file(shp_path)
        if len(gdf) == 0:
            return None, "Shapefile пустой."
        if gdf.crs is None:
            gdf = gdf.set_crs(epsg=int(fallback_epsg))
        if gdf.crs.to_epsg() != 4326:
            gdf = gdf.to_crs(epsg=4326)
        try:
            gdf["geometry"] = gdf.geometry.simplify(0.00005)
        except Exception:
            pass
        return gdf.__geo_interface__, None
    except Exception as e:
        return None, f"Ошибка чтения shapefile: {e}"

# ============================================================
# 6. КАРТА
# ============================================================
def make_interactive_map(
    towers_df: pd.DataFrame,
    result: dict | None,
    map_style: str = "Гибрид (Google)",
    selected_names: list | None = None,
    quarters_geojson: dict | None = None,
):
    selected_names = selected_names or []

    lats, lons = [], []
    if towers_df is not None and len(towers_df) > 0:
        lats.extend(towers_df["Широта_dec"].tolist())
        lons.extend(towers_df["Долгота_dec"].tolist())
    if result:
        lats.append(result["lat"])
        lons.append(result["lon"])
    center, zoom = calc_map_view(lats, lons)

    tile_info = MAP_TILES.get(map_style, MAP_TILES["Гибрид (Google)"])
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles=tile_info["url"],
        attr=tile_info["attr"],
        control_scale=True,
    )

    if quarters_geojson:
        fg_quarters = folium.FeatureGroup(name="Квартальная сеть")
        feats = quarters_geojson.get("features", [])
        fields = list((feats[0].get("properties") or {}).keys())[:4] if feats else []
        folium.GeoJson(
            quarters_geojson,
            style_function=lambda feature: {
                "color": "#e040fb", "weight": 1.2, "opacity": 0.75, "fill": False,
            },
            tooltip=folium.GeoJsonTooltip(fields=fields) if fields else None,
        ).add_to(fg_quarters)
        fg_quarters.add_to(m)

    fg_towers = folium.FeatureGroup(name="Вышки")
    for _, row in towers_df.iterrows():
        name = str(row["Наименование Вышки"])
        is_selected = name in selected_names
        color = "green" if is_selected else "blue"
        popup_html = f"""
        <div style="font-family: Arial; color: #111;">
            <b>{name}</b><br>
            Лесхоз: {row['Лесхоз']}<br>
            Координаты: {row['Широта_dec']:.6f}, {row['Долгота_dec']:.6f}
        </div>
        """
        folium.Marker(
            [row["Широта_dec"], row["Долгота_dec"]],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=name,
            icon=folium.Icon(color=color, icon="signal", prefix="fa"),
        ).add_to(fg_towers)
    fg_towers.add_to(m)

    if result:
        fg_bearings = folium.FeatureGroup(name="Азимуты")
        for b in result["bearings"]:
            dist = b.get("distance")
            dist_text = format_distance(dist) if dist is not None else "—"
            folium.PolyLine(
                [[b["lat"], b["lon"]], [result["lat"], result["lon"]]],
                color="#ff9800", weight=3, opacity=0.85,
                tooltip=f"{b['name']}: азимут {b['azimuth']}°, {dist_text}",
                popup=(
                    f"<b>{b['name']}</b><br>"
                    f"Азимут: {b['azimuth']}°<br>"
                    f"Расстояние до очага: {dist_text}"
                ),
            ).add_to(fg_bearings)
            mid_lat = (b["lat"] + result["lat"]) / 2
            mid_lon = (b["lon"] + result["lon"]) / 2
            label_html = (
                f'<div style="transform: translate(-50%, -50%); '
                f'background: rgba(22,27,34,0.85); color: #ffd54f; '
                f'border: 1px solid rgba(255,152,0,0.6); border-radius: 10px; '
                f'padding: 2px 8px; font-size: 11px; font-weight: 600; '
                f'font-family: Arial, sans-serif; white-space: nowrap; '
                f'box-shadow: 0 1px 4px rgba(0,0,0,0.5);">{dist_text}</div>'
            )
            folium.Marker(
                [mid_lat, mid_lon],
                icon=folium.DivIcon(
                    html=label_html, icon_size=(0, 0), class_name=""
                ),
                tooltip=f"{b['name']}: {dist_text}",
            ).add_to(fg_bearings)
        fg_bearings.add_to(m)

        fg_fire = folium.FeatureGroup(name="Очаг")
        folium.Marker(
            [result["lat"], result["lon"]],
            popup=f"""
            <div style="font-family: Arial; color: #111;">
                🔥 <b>Расчётный очаг</b><br>
                Широта: {result['lat']:.6f}<br>
                Долгота: {result['lon']:.6f}<br>
                Погрешность: {result['error_radius']:.0f} м
            </div>
            """,
            tooltip="🔥 Расчётная точка пожара",
            icon=folium.Icon(color="red", icon="fire", prefix="fa"),
        ).add_to(fg_fire)
        fg_fire.add_to(m)

        fg_error = folium.FeatureGroup(name="Зона погрешности")
        folium.Circle(
            [result["lat"], result["lon"]],
            radius=result["error_radius"],
            color="#d32f2f", weight=2,
            fill=True, fill_color="#d32f2f", fill_opacity=0.15,
            popup=f"Зона погрешности: {result['error_radius']:.0f} м",
        ).add_to(fg_error)
        fg_error.add_to(m)

    legend_items = [
        ('<span style="color:#1976d2;">●</span>', "Вышка"),
        ('<span style="color:#2e7d32;">●</span>', "Выбранная вышка"),
    ]
    if quarters_geojson:
        legend_items.append(('<span style="color:#e040fb;">▭</span>', "Квартальная сеть"))
    legend_items.extend([
        ('<span style="color:#ff9800;">—</span>', "Азимут"),
        ('<span style="color:#ffd54f;">▬</span>', "Расстояние до очага"),
        ('<span style="color:#d32f2f;">●</span>', "Очаг"),
        ('<span style="color:#d32f2f;">○</span>', "Зона погрешности"),
    ])
    legend_html = '<div class="map-legend">' + "".join(
        f'<div class="map-legend-item">{icon} {label}</div>'
        for icon, label in legend_items
    ) + '</div>'
    m.get_root().html.add_child(folium.Element(legend_html))
    folium.LayerControl(collapsed=False).add_to(m)
    return m

def generate_static_map(towers_df: pd.DataFrame, result: dict | None, width=900, height=650):
    m = StaticMap(width, height)
    for _, row in towers_df.iterrows():
        m.add_marker(CircleMarker((row["Долгота_dec"], row["Широта_dec"]), "#2196F3", 8))
    if result:
        for b in result["bearings"]:
            m.add_line(
                Line([(b["lon"], b["lat"]), (result["lon"], result["lat"])], "#FF9800", 3)
            )
        m.add_marker(CircleMarker((result["lon"], result["lat"]), "#F44336", 15))
        lat_rad = math.radians(result["lat"])
        r_lat = result["error_radius"] / 111320
        r_lon = result["error_radius"] / (111320 * math.cos(lat_rad))
        circle_points = []
        for i in range(36):
            angle = math.radians(i * 10)
            circle_points.append((
                result["lon"] + r_lon * math.cos(angle),
                result["lat"] + r_lat * math.sin(angle),
            ))
        m.add_line(Line(circle_points, "#F44336", 2))
    image = m.render()
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()

# ============================================================
# 7. СОСТОЯНИЕ СЕССИИ
# ============================================================
def init_session_state():
    defaults = {
        "towers": None, "source_name": None, "load_error": None,
        "result": None, "selected_names": [], "map_style": "Гибрид (Google)",
        "history": [], "threshold_good": 300.0, "threshold_warn": 1000.0,
        "tower_multiselect": [], "quarters_geojson": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

def try_load_default_file():
    if st.session_state.towers is None and os.path.exists(DEFAULT_FILE):
        df, err = read_excel_safe(DEFAULT_FILE)
        if df is not None:
            st.session_state.towers = df
            st.session_state.source_name = DEFAULT_FILE
            st.session_state.load_error = None
        else:
            st.session_state.load_error = err

def reset_session_data():
    for key in [
        "towers", "source_name", "load_error", "result",
        "selected_names", "history", "tower_multiselect", "quarters_geojson",
    ]:
        st.session_state.pop(key, None)

# ============================================================
# 8. ЗАГОЛОВОК
# ============================================================
def render_header():
    status_text, status_tone = get_system_status()
    source = st.session_state.get("source_name") or "Источник не загружен"
    st.markdown(
        f"""
        <div class="dash-header">
            <div>
                <div class="dash-header-title">Система мониторинга лесных пожаров</div>
                <div class="dash-header-sub">Центр триангуляции и прогнозирования</div>
            </div>
            <div style="text-align: right;">
                <div class="status-badge status-{status_tone}">
                    {'⚠️' if status_tone != 'ok' else '✅'} {status_text}
                </div>
                <div style="font-size: 0.75rem; opacity: 0.6; margin-top: 6px;">
                    Источник: {source}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# ============================================================
# 9. KPI-СТРОКА
# ============================================================
def render_kpi():
    towers = st.session_state.get("towers")
    result = st.session_state.get("result")
    selected_count = len(st.session_state.get("selected_names", []))
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        kpi_card("Вышек в базе", str(len(towers) if towers is not None else 0), "загруженные координаты")
    with c2:
        tone = "ok" if selected_count >= 2 else "warn"
        kpi_card("Выбрано", str(selected_count), "минимум 2 для расчёта", tone=tone)
    if result:
        with c3:
            kpi_card("Широта", f"{result['lat']:.5f}°", "WGS84")
        with c4:
            kpi_card("Долгота", f"{result['lon']:.5f}°", "WGS84")
        with c5:
            accuracy_text, accuracy_tone = get_accuracy(result)
            kpi_card(
                "Погрешность",
                format_distance(result["error_radius"]),
                accuracy_text,
                tone=accuracy_tone,
            )
    else:
        with c3:
            kpi_card("Широта", "—", "нет расчёта")
        with c4:
            kpi_card("Долгота", "—", "нет расчёта")
        with c5:
            kpi_card("Погрешность", "—", "нет расчёта")

# ============================================================
# 10. ВКЛАДКА: КАРТА
# ============================================================
def render_map_tab(towers: pd.DataFrame, result: dict | None):
    map_options = list(MAP_TILES.keys())
    default_idx = (
        map_options.index(st.session_state.map_style)
        if st.session_state.map_style in map_options else 0
    )
    map_style = st.selectbox(
        "Подложка карты", map_options, index=default_idx, key="map_style_selector"
    )
    st.session_state.map_style = map_style
    st.markdown('<div class="map-container">', unsafe_allow_html=True)
    m = make_interactive_map(
        towers,
        result,
        st.session_state.map_style,
        st.session_state.selected_names,
        quarters_geojson=st.session_state.get("quarters_geojson"),
    )
    st_folium(m, height=720, use_container_width=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ============================================================
# 11. ВКЛАДКА: ВВОД АЗИМУТОВ (ИСПРАВЛЕНЫ CALLBACK'И И width="stretch")
# ============================================================
def _reset_azimuths_cb(names: list):
    for name in names:
        key = f"az_{name}"
        if key in st.session_state:
            st.session_state[key] = 0.0

def _select_all_cb(names: list):
    st.session_state.tower_multiselect = list(names)
    st.session_state.selected_names = list(names)

def _clear_selection_cb():
    st.session_state.tower_multiselect = []
    st.session_state.selected_names = []

def render_input_tab(towers: pd.DataFrame, tri: Triangulator):
    left, right = st.columns([2, 3])
    with left:
        st.markdown("### 🔍 Фильтры и выбор вышек")
        search = st.text_input("Поиск", placeholder="Название вышки или лесхоз", key="tower_search")

        forest_values = sorted(towers["Лесхоз"].dropna().astype(str).unique().tolist())
        forest_options = ["Все"] + forest_values
        forest = st.selectbox("Лесхоз", forest_options, key="forest_filter")

        mask = pd.Series(True, index=towers.index)
        if search:
            mask &= (
                towers["Наименование Вышки"].astype(str).str.contains(search, case=False, na=False)
                | towers["Лесхоз"].astype(str).str.contains(search, case=False, na=False)
            )
        if forest != "Все":
            mask &= towers["Лесхоз"].astype(str) == forest

        filtered = towers[mask]
        filtered_names = filtered["Наименование Вышки"].astype(str).tolist()

        current_selected = st.session_state.selected_names
        extra_selected = [x for x in current_selected if x not in filtered_names]
        options = filtered_names + extra_selected

        if "tower_multiselect" not in st.session_state:
            st.session_state.tower_multiselect = list(current_selected)
        st.session_state.tower_multiselect = [
            x for x in st.session_state.tower_multiselect if x in options
        ]

        selected = st.multiselect(
            "Выберите вышки",
            options=options,
            key="tower_multiselect",
        )
        if selected != st.session_state.selected_names:
            st.session_state.selected_names = list(selected)

        st.caption(f"Выбрано вышек: {len(selected)}")

        b1, b2 = st.columns(2)
        with b1:
            st.button(
                "Выбрать все",
                on_click=_select_all_cb,
                args=(filtered_names,),
                width="stretch",
            )
        with b2:
            st.button(
                "Очистить",
                on_click=_clear_selection_cb,
                width="stretch",
            )

        if len(selected) < 2:
            st.warning("Выберите минимум 2 вышки.")
        else:
            st.success("Достаточно вышек для расчёта.")

    with right:
        st.markdown("### 📡 Азимуты")
        selected = st.session_state.selected_names
        if not selected:
            st.info("Выберите вышки слева и укажите азимуты.")
            return

        with st.form("azimuth_form", clear_on_submit=False):
            azimuths = {}
            for name in selected:
                default_az = float(st.session_state.get(f"az_{name}", 0.0))
                az = st.number_input(
                    f"Азимут: {name}",
                    min_value=0.0, max_value=360.0,
                    value=default_az, step=0.1,
                    key=f"az_{name}",
                )
                azimuths[name] = float(az) % 360.0
            c1, c2 = st.columns([2, 1])
            calc_button = c1.form_submit_button(
                "🎯 Рассчитать", type="primary", width="stretch"
            )
            reset_az_button = c2.form_submit_button(
                "🔄 Сбросить азимуты",
                on_click=_reset_azimuths_cb,
                args=(list(selected),),
                width="stretch",
            )

        if calc_button:
            if len(azimuths) < 2:
                st.warning("Нужно минимум 2 вышки с азимутами.")
            else:
                with st.spinner("Выполняется расчёт..."):
                    result = tri.calc(azimuths)
                if result:
                    st.session_state.result = result
                    st.session_state.history.append({
                        "Время": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "Широта": result["lat"],
                        "Долгота": result["lon"],
                        "Погрешность, м": round(result["error_radius"], 1),
                        "RMSE, м": round(result["rmse"], 1),
                        "Вышек": result["n_towers"],
                    })
                    st.session_state.history = st.session_state.history[-50:]
                    st.success("✅ Расчёт выполнен. Карта обновлена.")
                    st.rerun()
                else:
                    st.error("Не удалось выполнить расчёт. Проверьте азимуты.")

# ============================================================
# 12. ВКЛАДКА: ОТЧЁТ
# ============================================================
def render_report_tab(towers: pd.DataFrame, result: dict | None):
    if not result:
        st.info("Сначала выполните расчёт во вкладке «Ввод азимутов».")
        return
    accuracy_text, accuracy_tone = get_accuracy(result)
    if accuracy_tone == "ok":
        st.success(f"Очаг рассчитан. Точность: {accuracy_text.lower()}.")
    elif accuracy_tone == "warn":
        st.warning(f"Очаг рассчитан. Точность: {accuracy_text.lower()}.")
    else:
        st.error(f"Очаг рассчитан. Точность: {accuracy_text.lower()}.")

    c1, c2, c3, c4 = st.columns(4)
    with c1: st.metric("Широта", f"{result['lat']:.6f}°")
    with c2: st.metric("Долгота", f"{result['lon']:.6f}°")
    with c3: st.metric("Погрешность", format_distance(result["error_radius"]))
    with c4: st.metric("RMSE", format_distance(result["rmse"]))

    st.markdown("---")
    st.markdown("### Участвующие вышки")
    bearing_rows = [
        {
            "Вышка": b["name"],
            "Азимут": f"{b['azimuth']}°",
            "Расстояние до очага": format_distance(b.get("distance")),
        }
        for b in result["bearings"]
    ]
    st.dataframe(pd.DataFrame(bearing_rows), use_container_width=True)
    st.markdown("---")

    if st.button("💾 Сформировать отчёт", type="primary", width="stretch"):
        with st.spinner("Генерация файлов..."):
            png_bytes = generate_static_map(towers, result)
            html_map = make_interactive_map(
                towers, result, st.session_state.map_style,
                [b["name"] for b in result["bearings"]],
                quarters_geojson=st.session_state.get("quarters_geojson"),
            )
            html_bytes = html_map.get_root().render().encode("utf-8")
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        gmaps_link = f"https://www.google.com/maps?q={result['lat']:.6f},{result['lon']:.6f}"
        report_lines = [
            "ОТЧЁТ О ПОЖАРЕ", "==============================",
            f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", "",
            "КООРДИНАТЫ ПОЖАРА:",
            f"Широта: {result['lat']:.6f}", f"Долгота: {result['lon']:.6f}",
            f"Ссылка Google Maps: {gmaps_link}", "",
            "ТОЧНОСТЬ:",
            f"Погрешность: {result['error_radius']:.0f} м",
            f"RMSE: {result['rmse']:.0f} м",
            f"Оценка точности: {accuracy_text}",
            f"Вышек задействовано: {result['n_towers']}", "",
            "АЗИМУТЫ:",
        ]
        for b in result["bearings"]:
            dist_text = format_distance(b.get("distance"))
            report_lines.append(f"  • {b['name']}: {b['azimuth']}° — {dist_text}")
        report_text = "\n".join(report_lines)

        st.markdown("### Превью карты")
        st.image(png_bytes, caption="Статическая карта", use_container_width=True)
        st.markdown("### Скачать файлы")
        d1, d2, d3 = st.columns(3)
        with d1:
            st.download_button(
                "📄 .TXT", report_text.encode("utf-8"),
                f"otchet_{ts}.txt", "text/plain", width="stretch",
            )
        with d2:
            st.download_button(
                "🖼️ .PNG", png_bytes,
                f"karta_{ts}.png", "image/png", width="stretch",
            )
        with d3:
            st.download_button(
                "🌐 .HTML", html_bytes,
                f"karta_{ts}.html", "text/html", width="stretch",
            )
        st.success("Файлы готовы к скачиванию.")

    st.markdown("---")
    st.markdown("### История расчётов")
    if st.session_state.history:
        history_df = pd.DataFrame(st.session_state.history).iloc[::-1]
        st.dataframe(history_df, use_container_width=True)
    else:
        st.info("История расчётов пока пуста.")

# ============================================================
# 13. ВКЛАДКА: ВЫШКИ
# ============================================================
def render_data_tab(towers: pd.DataFrame):
    search = st.text_input("Поиск по таблице", placeholder="Название вышки или лесхоз", key="data_tab_search")
    view = towers.copy()
    if search:
        mask = (
            view["Наименование Вышки"].astype(str).str.contains(search, case=False, na=False)
            | view["Лесхоз"].astype(str).str.contains(search, case=False, na=False)
        )
        view = view[mask]
    st.dataframe(view, use_container_width=True)
    st.download_button(
        "Скачать таблицу CSV", view.to_csv(index=False).encode("utf-8"),
        "towers_export.csv", "text/csv", width="stretch",
    )

# ============================================================
# 14. ВКЛАДКА: НАСТРОЙКИ И ЗАГРУЗКА ДАННЫХ
# ============================================================
def render_settings_tab():
    st.markdown(f"Текущий источник: `{st.session_state.source_name or 'не загружен'}`")
    if st.session_state.load_error:
        st.warning(f"Ошибка загрузки: {st.session_state.load_error}")

    st.markdown("### Загрузить файл")
    uploaded = st.file_uploader(
        "Excel-файл со списком вышек", type=["xlsx", "xls"],
        help="Нужны столбцы: Лесхоз, Наименование Вышки, Широта, Долгота",
    )
    if uploaded is not None:
        if st.button("Загрузить выбранный файл", type="primary", width="stretch"):
            uploaded.seek(0)
            df, err = read_excel_safe(uploaded)
            if df is not None:
                st.session_state.towers = df
                st.session_state.source_name = uploaded.name
                st.session_state.load_error = None
                st.session_state.result = None
                st.session_state.selected_names = []
                st.session_state.tower_multiselect = []
                st.success(f"Файл загружен. Вышек: {len(df)}")
                st.rerun()
            else:
                st.session_state.load_error = err
                st.error(err)

    default_exists = os.path.exists(DEFAULT_FILE)
    st.markdown("### Стандартный файл")
    if st.button(
        f"Загрузить стандартный файл: {DEFAULT_FILE}",
        disabled=not default_exists, width="stretch",
    ):
        df, err = read_excel_safe(DEFAULT_FILE)
        if df is not None:
            st.session_state.towers = df
            st.session_state.source_name = DEFAULT_FILE
            st.session_state.load_error = None
            st.session_state.result = None
            st.session_state.selected_names = []
            st.session_state.tower_multiselect = []
            st.success(f"Файл загружен. Вышек: {len(df)}")
            st.rerun()
        else:
            st.session_state.load_error = err
            st.error(err)
    if not default_exists:
        st.caption(f"Файл {DEFAULT_FILE} не найден в папке с приложением.")

    st.markdown("---")
    st.markdown("### Пороги точности")
    c1, c2 = st.columns(2)
    with c1:
        st.number_input("Высокая точность до, м", min_value=10.0, max_value=10000.0, step=10.0, key="threshold_good")
    with c2:
        st.number_input("Средняя точность до, м", min_value=50.0, max_value=50000.0, step=50.0, key="threshold_warn")
    st.caption("Если погрешность меньше первого порога — точность высокая, меньше второго — средняя, иначе — низкая.")

    st.markdown("---")
    st.markdown("### Квартальная сеть (shapefile)")
    st.caption("ZIP-архив с набором .shp + .dbf + .shx + .prj либо путь к .shp на диске.")
    q_zip = st.file_uploader("Shapefile в ZIP-архиве", type=["zip"], key="quarters_zip")
    q_path = st.text_input("Или путь к .shp на диске", key="quarters_path", placeholder="D:/GIS/kvartaly.shp")
    q_epsg = st.number_input(
        "EPSG, если в файле нет CRS (отсутствует .prj)",
        min_value=1000, max_value=99999, value=4326, step=1, key="quarters_epsg",
    )
    qc1, qc2 = st.columns(2)
    with qc1:
        if st.button("🗺️ Загрузить квартальную сеть", width="stretch"):
            src = q_zip.getvalue() if q_zip is not None else (q_path.strip() or None)
            if src is None:
                st.warning("Выберите ZIP-архив или укажите путь к .shp.")
            else:
                gj, err = load_quarters_geojson(src, fallback_epsg=int(q_epsg))
                if err:
                    st.error(err)
                else:
                    st.session_state.quarters_geojson = gj
                    st.success(f"Слой загружен. Объектов: {len(gj.get('features', []))}")
                    st.rerun()
    with qc2:
        if st.button("🗑️ Убрать слой", width="stretch"):
            st.session_state.quarters_geojson = None
            st.rerun()
    if st.session_state.get("quarters_geojson"):
        st.caption(f"Слой активен. Объектов: {len(st.session_state.quarters_geojson.get('features', []))}")

    st.markdown("---")
    if st.button("Полный сброс данных", width="stretch"):
        reset_session_data()
        st.rerun()

# ============================================================
# 15. ГЛАВНАЯ ФУНКЦИЯ
# ============================================================
def main():
    inject_css()
    init_session_state()
    try_load_default_file()
    render_header()
    render_kpi()
    towers = st.session_state.towers
    if towers is None or len(towers) == 0:
        st.error("Нет данных о вышках. Загрузите Excel-файл ниже или положите файл рядом с приложением.")
        render_settings_tab()
        st.stop()
    tri = Triangulator(towers)
    tab_map, tab_input, tab_report, tab_data, tab_settings = st.tabs([
        "🗺️ Карта", "📡 Ввод азимутов", "📊 Отчёт", "📋 Вышки", "⚙️ Настройки"
    ])
    with tab_map:
        render_map_tab(towers, st.session_state.result)
    with tab_input:
        render_input_tab(towers, tri)
    with tab_report:
        render_report_tab(towers, st.session_state.result)
    with tab_data:
        render_data_tab(towers)
    with tab_settings:
        render_settings_tab()

if __name__ == "__main__":
    main()
