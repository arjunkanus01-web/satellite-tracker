from __future__ import annotations

import os
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock

import numpy as np
import plotly.graph_objects as go
from PIL import Image
from skyfield.api import EarthSatellite, load, wgs84
from dash import Dash, Input, Output, State, dcc, html, no_update


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

EARTH_IMAGE = BASE_DIR / "earth.jpg"
TLE_FILE = BASE_DIR / "iss.tle"

TLE_URL = (
    "https://celestrak.org/NORAD/elements/gp.php"
    "?CATNR=25544&FORMAT=TLE"
)

NORAD_ID = "25544"

TLE_REFRESH_SECONDS = int(
    float(os.getenv("TLE_REFRESH_HOURS", "6")) * 3600
)

TLE_LOCK = Lock()

ts = load.timescale()

satellite = None
tle_status = "TLE not loaded"

last_tle_update = 0.0
last_failed_tle_attempt = 0.0
next_tle_retry = 0.0


# ============================================================
# TLE DOWNLOAD AND CACHE
# ============================================================

def valid_iss_tle(text):

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for i in range(len(lines) - 2):

        name, line1, line2 = lines[i:i + 3]

        if (
            line1.startswith("1 ")
            and line2.startswith("2 ")
            and line1[2:7].strip() == NORAD_ID
            and line2[2:7].strip() == NORAD_ID
        ):
            return name.removeprefix("0 "), line1, line2

    for i in range(len(lines) - 1):

        line1, line2 = lines[i:i + 2]

        if (
            line1.startswith("1 ")
            and line2.startswith("2 ")
            and line1[2:7].strip() == NORAD_ID
            and line2[2:7].strip() == NORAD_ID
        ):
            return "ISS (ZARYA)", line1, line2

    raise ValueError("Invalid ISS TLE data")


def read_cached_tle():

    if not TLE_FILE.exists():
        return None

    try:
        return valid_iss_tle(
            TLE_FILE.read_text(encoding="utf-8")
        )

    except (OSError, ValueError):
        return None


def download_tle():

    request = urllib.request.Request(
        TLE_URL,
        headers={
            "User-Agent": "TERRA-ISS-Tracker/1.0"
        },
    )

    with urllib.request.urlopen(
        request,
        timeout=12
    ) as response:

        content = response.read().decode(
            "utf-8",
            errors="replace"
        )

    result = valid_iss_tle(content)

    name, line1, line2 = result

    temporary_file = TLE_FILE.with_suffix(".tmp")

    temporary_file.write_text(
        f"{name}\n{line1}\n{line2}\n",
        encoding="utf-8"
    )

    temporary_file.replace(TLE_FILE)

    return result


def load_iss_satellite(force_refresh=False):

    global satellite
    global tle_status
    global last_tle_update
    global last_failed_tle_attempt

    with TLE_LOCK:

        now = time.time()

        cached = read_cached_tle()

        cache_exists = cached is not None

        cache_is_fresh = (
            cache_exists
            and now - TLE_FILE.stat().st_mtime
            < TLE_REFRESH_SECONDS
        )

        # Use fresh cache.
        if cache_is_fresh and not force_refresh:

            name, line1, line2 = cached

            satellite = EarthSatellite(
                line1, line2, name, ts
            )

            tle_status = "Using cached ISS TLE"

            last_tle_update = TLE_FILE.stat().st_mtime

            return satellite, tle_status

        # Avoid repeatedly contacting CelesTrak.
        if (
            cache_exists
            and not force_refresh
            and now - last_failed_tle_attempt < 300
        ):

            name, line1, line2 = cached

            satellite = EarthSatellite(
                line1, line2, name, ts
            )

            tle_status = (
                "Using saved TLE — next refresh scheduled"
            )

            last_tle_update = TLE_FILE.stat().st_mtime

            return satellite, tle_status

        try:

            name, line1, line2 = download_tle()

            satellite = EarthSatellite(
                line1, line2, name, ts
            )

            tle_status = (
                "Live TLE downloaded from CelesTrak"
            )

            last_tle_update = time.time()

            last_failed_tle_attempt = 0.0

            return satellite, tle_status

        except Exception as exc:

            last_failed_tle_attempt = now

            if cache_exists:

                name, line1, line2 = cached

                satellite = EarthSatellite(
                    line1, line2, name, ts
                )

                tle_status = (
                    "Using saved TLE — refresh failed "
                    f"({type(exc).__name__})"
                )

                last_tle_update = TLE_FILE.stat().st_mtime

                return satellite, tle_status

            raise RuntimeError(
                "ISS data is temporarily unavailable. "
                "The Earth view will still start, and "
                "TERRA will retry the orbital-data download."
            ) from exc


# ============================================================
# EARTH MODEL
# ============================================================

def earth_trace():

    if not EARTH_IMAGE.exists():

        raise FileNotFoundError(
            "Missing earth.jpg. Put it beside app.py."
        )

    image = Image.open(
        EARTH_IMAGE
    ).convert("RGB")

    image = image.resize(
        (360, 180),
        Image.Resampling.LANCZOS
    )

    pixels = np.asarray(image)

    lon = np.linspace(-np.pi, np.pi, 180)

    lat = np.linspace(
        -np.pi / 2,
        np.pi / 2,
        90
    )

    lon_grid, lat_grid = np.meshgrid(
        lon, lat
    )

    x = np.cos(lat_grid) * np.cos(lon_grid)

    y = np.cos(lat_grid) * np.sin(lon_grid)

    z = np.sin(lat_grid)

    px = np.clip(
        (
            (lon_grid + np.pi)
            / (2 * np.pi)
            * (pixels.shape[1] - 1)
        ).astype(int),
        0,
        pixels.shape[1] - 1
    )

    py = np.clip(
        (
            (np.pi / 2 - lat_grid)
            / np.pi
            * (pixels.shape[0] - 1)
        ).astype(int),
        0,
        pixels.shape[0] - 1
    )

    rgb = pixels[py, px]

    vertex_colours = [
        f"rgb({r},{g},{b})"
        for r, g, b in rgb.reshape(-1, 3)
    ]

    rows, cols = x.shape

    ii, jj, kk = [], [], []

    for row in range(rows - 1):

        for col in range(cols - 1):

            a = row * cols + col
            b = a + 1
            c = a + cols
            d = c + 1

            # Two triangles per mesh cell.
            ii.extend((a, b))
            jj.extend((b, d))
            kk.extend((c, c))

    return go.Mesh3d(
        x=x.ravel(),
        y=y.ravel(),
        z=z.ravel(),

        i=ii,
        j=jj,
        k=kk,

        vertexcolor=vertex_colours,

        name="Earth",

        flatshading=False,

        lighting=dict(
            ambient=0.72,
            diffuse=0.65,
            specular=0.18,
            roughness=0.85,
            fresnel=0.08
        ),

        lightposition=dict(
            x=100,
            y=200,
            z=100
        ),

        hoverinfo="skip",
        showscale=False
    )


# ============================================================
# ATMOSPHERE
# ============================================================

def sphere_shell(
    radius,
    colour,
    opacity,
    name
):

    u = np.linspace(
        0,
        2 * np.pi,
        48
    )

    v = np.linspace(
        0,
        np.pi,
        24
    )

    uu, vv = np.meshgrid(u, v)

    return go.Surface(

        x=radius * np.cos(uu) * np.sin(vv),

        y=radius * np.sin(uu) * np.sin(vv),

        z=radius * np.cos(vv),

        colorscale=[
            [0, colour],
            [1, colour]
        ],

        opacity=opacity,

        showscale=False,

        hoverinfo="skip",

        name=name
    )


# ============================================================
# STAR FIELD
# ============================================================

def star_trace():

    rng = np.random.default_rng(42)

    count = 420

    points = rng.uniform(
        -8,
        8,
        (count, 3)
    )

    distances = np.linalg.norm(
        points,
        axis=1
    )

    points = points[distances > 2.2]

    return go.Scatter3d(

        x=points[:, 0],
        y=points[:, 1],
        z=points[:, 2],

        mode="markers",

        marker=dict(
            size=1.25,
            color="#DCEBFF",
            opacity=0.8
        ),

        name="Stars",

        hoverinfo="skip"
    )


# ============================================================
# COORDINATE CONVERSION
# ============================================================

def geo_to_xyz(
    latitude_deg,
    longitude_deg,
    altitude_km=0.0
):

    lat = np.radians(
        np.asarray(latitude_deg, dtype=float)
    )

    lon = np.radians(
        np.asarray(longitude_deg, dtype=float)
    )

    radius = (
        1.0
        + np.asarray(altitude_km, dtype=float)
        / 6371.0
    )

    x = radius * np.cos(lat) * np.cos(lon)

    y = radius * np.cos(lat) * np.sin(lon)

    z = radius * np.sin(lat)

    return x, y, z


# ============================================================
# CURRENT ISS POSITION
# ============================================================

def calculate_iss_state(sat):

    now = ts.now()

    geocentric = sat.at(now)

    point = wgs84.subpoint(geocentric)

    x, y, z = geo_to_xyz(
        point.latitude.degrees,
        point.longitude.degrees,
        point.elevation.km
    )

    return (
        now,
        point,
        (
            float(x),
            float(y),
            float(z)
        )
    )


# ============================================================
# FUTURE GROUND TRACK
# ============================================================

def calculate_orbit(sat, now):

    minutes = np.linspace(
        0,
        95,
        360
    )

    future_times = ts.tt_jd(
        now.tt + minutes / 1440.0
    )

    positions = sat.at(future_times)

    subpoints = wgs84.subpoint(
        positions
    )

    lat = subpoints.latitude.degrees

    lon = np.radians(
        subpoints.longitude.degrees
    )

    radius = (
        1.0
        + subpoints.elevation.km / 6371.0
    )

    x = (
        radius
        * np.cos(np.radians(lat))
        * np.cos(lon)
    )

    y = (
        radius
        * np.cos(np.radians(lat))
        * np.sin(lon)
    )

    z = (
        radius
        * np.sin(np.radians(lat))
    )

    # Break the line at the longitude seam.
    jumps = (
        np.where(
            np.abs(np.diff(lon)) > np.pi
        )[0] + 1
    )

    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    z = np.asarray(z, dtype=float)

    x[jumps] = np.nan
    y[jumps] = np.nan
    z[jumps] = np.nan

    return x, y, z


# ============================================================
# CREATE 3D FIGURE
# ============================================================

def make_figure(sat):

    traces = [

        star_trace(),

        sphere_shell(
            1.075,
            "#367CFF",
            0.045,
            "Outer atmosphere"
        ),

        sphere_shell(
            1.045,
            "#36A7FF",
            0.075,
            "Middle atmosphere"
        ),

        sphere_shell(
            1.018,
            "#A5DFFF",
            0.12,
            "Inner atmosphere"
        ),

        earth_trace()
    ]

    if sat is not None:

        now, point, iss_xyz = (
            calculate_iss_state(sat)
        )

        orbit_x, orbit_y, orbit_z = (
            calculate_orbit(sat, now)
        )

        orbit_trace = go.Scatter3d(

            x=orbit_x,
            y=orbit_y,
            z=orbit_z,

            mode="lines",

            line=dict(
                color="#FFB84D",
                width=3
            ),

            name="Predicted ground track",

            hoverinfo="skip",

            connectgaps=False
        )

        iss_trace = go.Scatter3d(

            x=[iss_xyz[0]],
            y=[iss_xyz[1]],
            z=[iss_xyz[2]],

            mode="markers+text",

            text=["ISS"],

            textposition="top center",

            textfont=dict(
                color="#FFFFFF",
                size=12
            ),

            marker=dict(
                size=7,
                color="#FFB84D",
                line=dict(
                    color="#FFFFFF",
                    width=1.2
                ),
                symbol="diamond"
            ),

            name="International Space Station",

            hovertemplate=(
                "<b>ISS</b><br>"
                f"Latitude: {point.latitude.degrees:.3f}°<br>"
                f"Longitude: {point.longitude.degrees:.3f}°<br>"
                f"Altitude: {point.elevation.km:.1f} km"
                "<extra></extra>"
            )
        )

        traces.extend([
            orbit_trace,
            iss_trace
        ])

    fig = go.Figure(
        data=traces
    )

    fig.update_layout(

        title=dict(
            text=(
                "TERRA "
                "<span style='font-size:13px;color:#9AAAC0'>"
                "/ LIVE EARTH & ISS TRACKER"
                "</span>"
            ),
            x=0.04,
            y=0.96,
            font=dict(
                size=22,
                color="#F4F7FC"
            )
        ),

        paper_bgcolor="#050914",
        plot_bgcolor="#050914",

        font=dict(
            color="#DCE6F5",
            family="Arial, sans-serif"
        ),

        margin=dict(
            l=0,
            r=0,
            t=62,
            b=0
        ),

        height=650,

        showlegend=True,

        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=0.01,
            xanchor="left",
            x=0.02,
            bgcolor="rgba(5,9,20,0.55)"
        ),

        scene=dict(

            bgcolor="#050914",

            xaxis=dict(
                visible=False,
                range=[-2.1, 2.1]
            ),

            yaxis=dict(
                visible=False,
                range=[-2.1, 2.1]
            ),

            zaxis=dict(
                visible=False,
                range=[-2.1, 2.1]
            ),

            aspectmode="cube",

            camera=dict(
                eye=dict(
                    x=1.65,
                    y=1.65,
                    z=1.05
                )
            )
        ),

        uirevision="terra-camera"
    )

    return fig


# ============================================================
# ISS PASS PREDICTION
# ============================================================

def predict_passes(
    sat,
    latitude,
    longitude
):

    if not -90 <= latitude <= 90:
        raise ValueError(
            "Latitude must be between -90 and 90."
        )

    if not -180 <= longitude <= 180:
        raise ValueError(
            "Longitude must be between -180 and 180."
        )

    observer = wgs84.latlon(
        latitude_degrees=latitude,
        longitude_degrees=longitude
    )

    start = ts.now()

    end = ts.from_datetime(
        datetime.now(timezone.utc)
        + timedelta(hours=24)
    )

    event_times, events = sat.find_events(
        observer,
        start,
        end,
        altitude_degrees=0.0
    )

    labels = {
        0: "Rise",
        1: "Highest point",
        2: "Set"
    }

    results = []

    for event_time, event in zip(
        event_times,
        events
    ):

        difference = sat - observer

        topocentric = difference.at(
            event_time
        )

        altitude, azimuth, _ = (
            topocentric.altaz()
        )

        results.append({

            "time": (
                event_time.utc_datetime().strftime(
                    "%d %b %Y, %H:%M:%S UTC"
                )
            ),

            "event": labels[int(event)],

            "altitude": float(
                altitude.degrees
            ),

            "azimuth": float(
                azimuth.degrees
            )
        })

    return results


# ============================================================
# INITIAL STARTUP
# ============================================================

try:

    initial_satellite, initial_tle_status = (
        load_iss_satellite()
    )

except Exception:

    initial_satellite = None

    initial_tle_status = (
        "Earth online — waiting for ISS orbital data; "
        "automatic retry enabled"
    )

    next_tle_retry = time.time() + 30


# ============================================================
# DASH APPLICATION
# ============================================================

app = Dash(__name__)

app.title = "TERRA — Live ISS Tracker"


CARD_STYLE = {

    "background": "#101A2B",

    "border": "1px solid #24344D",

    "borderRadius": "16px",

    "padding": "16px"
}


app.layout = html.Div(

    style={

        "minHeight": "100vh",

        "background": "#050914",

        "color": "#EAF1FC",

        "fontFamily": "Arial, sans-serif",

        "padding": "18px"
    },

    children=[

        html.Div(

            style={

                "maxWidth": "1500px",

                "margin": "0 auto"
            },

            children=[

                # HEADER

                html.Div(

                    style={

                        "display": "flex",

                        "justifyContent": "space-between",

                        "alignItems": "center",

                        "gap": "16px",

                        "flexWrap": "wrap",

                        "padding": "8px 4px 16px"
                    },

                    children=[

                        html.Div([

                            html.Div(

                                "T E R R A",

                                style={

                                    "fontSize": "28px",

                                    "fontWeight": "700",

                                    "letterSpacing": "5px"
                                }
                            ),

                            html.Div(

                                "EARTH OBSERVATION / ISS TRACKING",

                                style={

                                    "fontSize": "11px",

                                    "letterSpacing": "2px",

                                    "color": "#8EA5C5",

                                    "marginTop": "5px"
                                }
                            )
                        ]),

                        html.Div(

                            id="connection-status",

                            children=initial_tle_status,

                            style={

                                "color": "#9DB4D2",

                                "fontSize": "12px",

                                "padding": "9px 13px",

                                "border": "1px solid #263B58",

                                "borderRadius": "20px"
                            }
                        )
                    ]
                ),

                # EARTH GRAPH

                dcc.Graph(

                    id="earth-graph",

                    figure=make_figure(
                        initial_satellite
                    ),

                    config={

                        "displaylogo": False,

                        "scrollZoom": True,

                        "responsive": True
                    },

                    style={
                        "width": "100%"
                    }
                ),

                # LIVE DATA CARDS

                html.Div(

                    style={

                        "display": "grid",

                        "gridTemplateColumns": (
                            "repeat(auto-fit,minmax(210px,1fr))"
                        ),

                        "gap": "12px",

                        "marginTop": "12px"
                    },

                    children=[

                        html.Div([

                            html.Div(
                                "LATITUDE",
                                style={
                                    "fontSize": "10px",
                                    "color": "#8EA5C5"
                                }
                            ),

                            html.Div(
                                id="iss-lat",
                                children="—",
                                style={
                                    "fontSize": "22px",
                                    "marginTop": "8px"
                                }
                            )

                        ], style=CARD_STYLE),

                        html.Div([

                            html.Div(
                                "LONGITUDE",
                                style={
                                    "fontSize": "10px",
                                    "color": "#8EA5C5"
                                }
                            ),

                            html.Div(
                                id="iss-lon",
                                children="—",
                                style={
                                    "fontSize": "22px",
                                    "marginTop": "8px"
                                }
                            )

                        ], style=CARD_STYLE),

                        html.Div([

                            html.Div(
                                "ALTITUDE",
                                style={
                                    "fontSize": "10px",
                                    "color": "#8EA5C5"
                                }
                            ),

                            html.Div(
                                id="iss-alt",
                                children="—",
                                style={
                                    "fontSize": "22px",
                                    "marginTop": "8px"
                                }
                            )

                        ], style=CARD_STYLE),

                        html.Div([

                            html.Div(
                                "LAST POSITION UPDATE",
                                style={
                                    "fontSize": "10px",
                                    "color": "#8EA5C5"
                                }
                            ),

                            html.Div(
                                id="iss-time",
                                children="—",
                                style={
                                    "fontSize": "18px",
                                    "marginTop": "8px"
                                }
                            )

                        ], style=CARD_STYLE)
                    ]
                ),

                # PASS PREDICTION

                html.Div(

                    style={
                        **CARD_STYLE,
                        "marginTop": "18px"
                    },

                    children=[

                        html.Div(

                            "UPCOMING ISS PASSES",

                            style={
                                "fontSize": "14px",
                                "fontWeight": "700",
                                "letterSpacing": "1.5px"
                            }
                        ),

                        html.P(

                            "Enter your observer location to calculate "
                            "ISS horizon crossings over the next 24 hours.",

                            style={
                                "color": "#9DB0CA",
                                "fontSize": "12px"
                            }
                        ),

                        html.Div(

                            style={

                                "display": "flex",

                                "gap": "10px",

                                "flexWrap": "wrap",

                                "alignItems": "end"
                            },

                            children=[

                                html.Div([

                                    html.Label(
                                        "Latitude (−90 to 90°)"
                                    ),

                                    dcc.Input(

                                        id="observer-lat",

                                        type="number",

                                        min=-90,
                                        max=90,
                                        step="any",

                                        placeholder="e.g. 8.5",

                                        style={

                                            "display": "block",

                                            "marginTop": "6px",

                                            "padding": "10px",

                                            "borderRadius": "8px",

                                            "border": "1px solid #334967",

                                            "background": "#081222",

                                            "color": "white",

                                            "width": "180px"
                                        }
                                    )
                                ]),

                                html.Div([

                                    html.Label(
                                        "Longitude (−180 to 180°)"
                                    ),

                                    dcc.Input(

                                        id="observer-lon",

                                        type="number",

                                        min=-180,
                                        max=180,
                                        step="any",

                                        placeholder="e.g. 76.9",

                                        style={

                                            "display": "block",

                                            "marginTop": "6px",

                                            "padding": "10px",

                                            "borderRadius": "8px",

                                            "border": "1px solid #334967",

                                            "background": "#081222",

                                            "color": "white",

                                            "width": "180px"
                                        }
                                    )
                                ]),

                                html.Button(

                                    "Calculate passes",

                                    id="calculate-passes",

                                    n_clicks=0,

                                    style={

                                        "padding": "11px 18px",

                                        "border": "0",

                                        "borderRadius": "9px",

                                        "background": "#3978E8",

                                        "color": "white",

                                        "fontWeight": "600",

                                        "cursor": "pointer"
                                    }
                                )
                            ]
                        ),

                        html.Div(

                            id="pass-error",

                            style={
                                "color": "#FF9C9C",
                                "fontSize": "12px",
                                "marginTop": "12px"
                            }
                        ),

                        html.Div(
                            id="pass-results",
                            style={
                                "marginTop": "12px"
                            }
                        )
                    ]
                ),

                # FOOTER

                html.Div(

                    "Orbital positions are calculated using the latest "
                    "available TLE with Skyfield/SGP4. Pass predictions "
                    "use a 0° geometric horizon and do not account for "
                    "buildings, terrain, weather or sunlight visibility.",

                    style={

                        "color": "#7F91AA",

                        "fontSize": "11px",

                        "lineHeight": "1.6",

                        "padding": "18px 4px 8px"
                    }
                ),

                dcc.Interval(

                    id="live-tick",

                    interval=2000,

                    n_intervals=0
                )
            ]
        )
    ]
)


# ============================================================
# LIVE TRACKING CALLBACK
# ============================================================

@app.callback(

    Output("earth-graph", "figure"),

    Output("iss-lat", "children"),

    Output("iss-lon", "children"),

    Output("iss-alt", "children"),

    Output("iss-time", "children"),

    Output("connection-status", "children"),

    Input("live-tick", "n_intervals"),

    State("earth-graph", "figure")
)

def update_live_tracker(
    _n_intervals,
    current_figure
):

    global satellite
    global next_tle_retry

    # No ISS data yet: wait until the next retry.
    if satellite is None:

        if time.time() < next_tle_retry:

            return (
                no_update,
                no_update,
                no_update,
                no_update,
                no_update,
                "Earth online — waiting for ISS orbital data"
            )

        try:

            sat, status = load_iss_satellite()

            next_tle_retry = 0.0

            now, point, _xyz = (
                calculate_iss_state(sat)
            )

            return (

                make_figure(sat),

                f"{point.latitude.degrees:.3f}°",

                f"{point.longitude.degrees:.3f}°",

                f"{point.elevation.km:.1f} km",

                now.utc_datetime().strftime(
                    "%H:%M:%S UTC"
                ),

                status
            )

        except Exception as exc:

            next_tle_retry = time.time() + 300

            return (

                no_update,
                no_update,
                no_update,
                no_update,
                no_update,

                "Earth online — ISS data unavailable; "
                f"retrying in 5 minutes ({type(exc).__name__})"
            )

    try:

        sat, status = load_iss_satellite()

        now, point, xyz = (
            calculate_iss_state(sat)
        )

        orbit_x, orbit_y, orbit_z = (
            calculate_orbit(sat, now)
        )

        fig = go.Figure(
            current_figure
        )

        for trace in fig.data:

            if trace.name == "International Space Station":

                trace.x = [xyz[0]]
                trace.y = [xyz[1]]
                trace.z = [xyz[2]]

                trace.hovertemplate = (

                    "<b>ISS</b><br>"

                    f"Latitude: {point.latitude.degrees:.3f}°<br>"

                    f"Longitude: {point.longitude.degrees:.3f}°<br>"

                    f"Altitude: {point.elevation.km:.1f} km"

                    "<extra></extra>"
                )

            elif trace.name == "Predicted ground track":

                trace.x = orbit_x
                trace.y = orbit_y
                trace.z = orbit_z

        return (

            fig,

            f"{point.latitude.degrees:.3f}°",

            f"{point.longitude.degrees:.3f}°",

            f"{point.elevation.km:.1f} km",

            now.utc_datetime().strftime(
                "%H:%M:%S UTC"
            ),

            status
        )

    except Exception as exc:

        return (

            no_update,
            no_update,
            no_update,
            no_update,
            no_update,

            f"ISS update error: {type(exc).__name__}: {exc}"
        )


# ============================================================
# PASS PREDICTION CALLBACK
# ============================================================

@app.callback(

    Output("pass-results", "children"),

    Output("pass-error", "children"),

    Input("calculate-passes", "n_clicks"),

    State("observer-lat", "value"),

    State("observer-lon", "value"),

    prevent_initial_call=True
)

def calculate_observer_passes(
    _clicks,
    latitude,
    longitude
):

    if latitude is None or longitude is None:

        return (
            no_update,
            "Enter both latitude and longitude."
        )

    try:

        sat = satellite

        if sat is None:

            return (
                no_update,
                "ISS orbital data is not available yet. Try again shortly."
            )

        passes = predict_passes(
            sat,
            float(latitude),
            float(longitude)
        )

        if not passes:

            return (

                html.Div(
                    "No horizon crossing was found in the next 24 hours.",
                    style={
                        "color": "#AFC1D9",
                        "fontSize": "13px"
                    }
                ),

                ""
            )

        header = html.Tr([

            html.Th(
                "UTC time",
                style={"textAlign": "left", "padding": "9px"}
            ),

            html.Th(
                "Event",
                style={"textAlign": "left", "padding": "9px"}
            ),

            html.Th(
                "Altitude",
                style={"textAlign": "left", "padding": "9px"}
            ),

            html.Th(
                "Azimuth",
                style={"textAlign": "left", "padding": "9px"}
            )
        ])

        rows = [

            html.Tr([

                html.Td(
                    item["time"],
                    style={
                        "padding": "9px",
                        "borderTop": "1px solid #263B58"
                    }
                ),

                html.Td(
                    item["event"],
                    style={
                        "padding": "9px",
                        "borderTop": "1px solid #263B58"
                    }
                ),

                html.Td(
                    f'{item["altitude"]:.1f}°',
                    style={
                        "padding": "9px",
                        "borderTop": "1px solid #263B58"
                    }
                ),

                html.Td(
                    f'{item["azimuth"]:.1f}°',
                    style={
                        "padding": "9px",
                        "borderTop": "1px solid #263B58"
                    }
                )
            ])

            for item in passes
        ]

        return (

            html.Table(

                [
                    html.Thead(header),
                    html.Tbody(rows)
                ],

                style={

                    "width": "100%",

                    "borderCollapse": "collapse",

                    "fontSize": "12px",

                    "color": "#DCE6F5",

                    "textAlign": "left"
                }
            ),

            ""
        )

    except Exception as exc:

        return (
            no_update,
            f"Could not calculate passes: {exc}"
        )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    port = int(
        os.getenv("PORT", "8050")
    )

    app.run(

        host="0.0.0.0",

        port=port,

        debug=False
    )
