import numpy as np
import plotly.graph_objects as go
from PIL import Image
import time
from datetime import datetime,timezone
from skyfield.api import load,wgs84
from dash import Dash,dcc,html
from dash.dependencies import Input,Output
stations=load.tle_file(
    "https://celestrak.org/NORAD/elements/gp.php?CATNR=25544"
)
iss_satellite=next(
    sat for sat in stations
    if sat.model.satnum==25544
)
skyfield_timescale=load.timescale()
print("Loaded orbital data for:",iss_satellite.name)

# 1. Load the Earth texture
image = Image.open("earth.jpg").convert("RGB")
width, height = image.size
pixels = np.array(image)

# 2. Create sphere angles
u = np.linspace(-np.pi, np.pi, 360)
v = np.linspace(0, np.pi, 180)
lon, lat = np.meshgrid(u, v)

# 3. Convert angles into 3D coordinates
x = np.sin(lat) * np.cos(lon)
y = np.sin(lat) * np.sin(lon)
z = np.cos(lat)

# 4. Map Earth image pixels onto the sphere
px = np.clip(
    ((lon + np.pi) / (2 * np.pi) * (width - 1)).astype(int),
    0,
    width - 1
)

py = np.clip(
    (lat / np.pi * (height - 1)).astype(int),
    0,
    height - 1 
)

rgb = pixels[py, px]

# 5. Convert RGB values into Plotly colours
vertex_colours = [
    f"rgb({r},{g},{b})"
    for r, g, b in rgb.reshape(-1, 3)
]

# 6. Create triangles for the Earth mesh
rows, cols = x.shape
i, j, k = [], [], []

for row in range(rows - 1):
    for col in range(cols - 1):
        a = row * cols + col
        b = a + 1
        c = a + cols
        d = c + 1

        i.extend([a, a])
        j.extend([b, d])
        k.extend([c, c])

# 7. Build the textured Earth
earth = go.Mesh3d(
    x=x.flatten(),
    y=y.flatten(),
    z=z.flatten(),
    i=i,
    j=j,
    k=k,
    vertexcolor=vertex_colours,
    flatshading=False,
    name="Earth"
)

# 8. Create a blue atmospheric shell
outer_halo=go.Surface(
    x=1.075*x,
    y=1.075*y,
    z=1.075*z,
    surfacecolor=np.zeros_like(x),
    colorscale=[[0,"rgb(10,55,255)"],[1,"rgb(10,55,255)"]],
    opacity=0.055,
    showscale=False,
    hoverinfo="skip",
    name="Outer Halo"
)
middle_halo=go.Surface(
    x=1.045*x,
    y=1.045*y,
    z=1.045*z,
    surfacecolor=np.zeros_like(x),
    colorscale=[[0,"rgb(0,115,255)"],[1,"rgb(0,115,255)"]],
    opacity=0.10,
    showscale=False,
    hoverinfo="skip",
    name="Atmosphere"
)
inner_glow=go.Surface(
    x=1.018*x,
    y=1.018*y,z=1.018*z,
    surfacecolor=np.zeros_like(x),
    colorscale=[[0,"rgb(65,175,255)"],[1,"rgb(65,175,255)"]],
    opacity=0.16,
    showscale=False,
    hoverinfo="skip",
    name="Blue Limb"
)
np.random.seed(42)
star_count=1200
star_theta=np.random.uniform(0,2*np.pi,star_count)
star_z=np.random.uniform(-1,1,star_count)
np.random.seed(42)
star_count=700
star_x=np.random.uniform(-8,8,star_count)
star_y=np.random.uniform(-8,8,star_count)
star_z=np.random.uniform(-8,8,star_count)
distance=np.sqrt(star_x**2+star_y**2+star_z**2)
mask=distance>2.5
star_x=star_x[mask]
star_y=star_y[mask]
star_z=star_z[mask]
star_sizes=np.random.choice(
    [1,1.5,2],
    size=len(star_x),
    p=[0.65,0.27,0.08]
)
stars=go.Scatter3d(
    x=star_x,
    y=star_y,
    z=star_z,
    mode="markers",
    marker=dict(
        size=star_sizes,
        color="white",
        opacity=0.8
    ),
    name="Stars",
    hoverinfo="skip"
)
#Calculate ISS current position
now=skyfield_timescale.now()
geocentric=iss_satellite.at(now)
subpoint=wgs84.subpoint(geocentric)
iss_lat=np.radians(subpoint.latitude.degrees)
iss_lon=np.radians(subpoint.longitude.degrees)
iss_radius=1.0+subpoint.elevation.km/6371.0
iss_x = iss_radius * np.cos(iss_lat) * np.cos(iss_lon)
iss_y=iss_radius*np.cos(iss_lat)*np.sin(iss_lon)
iss_z = iss_radius * np.sin(iss_lat)
iss=go.Scatter3d(
    x=[iss_x],
    y=[iss_y],
    z=[iss_z],
    mode="markers+text",
    marker=dict(
        size=6,
        color="orange",
        line=dict(color="white",width=2)
    ),
    text=["ISS"],
    textposition="top center",
    textfont=dict(color="white",size=2),
    name="International Space Station",
    hovertemplate="ISS current position<extra></extra>"
)

#ISS orbital path
orbit_minutes=np.linspace(0,92.5,600)
orbit_times=skyfield_timescale.tt_jd(
    now.tt + orbit_minutes/1440.0
)
orbit_positions=iss_satellite.at(orbit_times)
orbit_subpoints=wgs84.subpoint(orbit_positions)
orbit_lat=np.radians(orbit_subpoints.latitude.degrees)
orbit_lon=np.radians(orbit_subpoints.longitude.degrees)
orbit_alt=orbit_subpoints.elevation.km
orbit_radius=1.0 + orbit_alt/6371.0
orbit_x=orbit_radius*np.cos(orbit_lat)*np.cos(orbit_lon)
orbit_y=orbit_radius*np.cos(orbit_lat)*np.sin(orbit_lon)
orbit_z=orbit_radius*np.sin(orbit_lat)
jumps=np.where(np.abs(np.diff(orbit_lon))>np.pi)[0]
orbit_x=orbit_x.astype(float)
orbit_y=orbit_y.astype(float)
orbit_z=orbit_z.astype(float)
for j in jumps:
    orbit_x[j+1]=np.nan
    orbit_y[j+1]=np.nan
    orbit_z[j+1]=np.nan
orbit=go.Scatter3d(
    x=orbit_x,
    y=orbit_y,
    z=orbit_z,
    mode="lines",
    line=dict(color="cyan",width=3),
    name="ISS Orbit",
    hoverinfo="skip",
    connectgaps=False
)
# 9. Display Earth and atmosphere
fig = go.Figure(data=[stars,outer_halo,middle_halo,inner_glow,orbit,earth,iss])
fig.update_layout(
    title="Terra - Earth and Atmosphere",
    scene=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        zaxis=dict(visible=False),
        aspectmode="data",
        dragmode="orbit",
        bgcolor="black",
        camera=dict(
            eye=dict(x=1.6, y=1.6, z=1.2)
        )
    ),
    paper_bgcolor="black",
    font=dict(color="white"),
    margin=dict(l=0, r=0, t=50, b=0)
)
fig.write_html(
    "index.html",
    include_plotlyjs=True,
    config={"scrollZoom": True}
)
