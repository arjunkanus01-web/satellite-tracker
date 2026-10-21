import numpy as np
import plotly.graph_objects as go
from PIL import Image
from urllib.request import urlopen
from skyfield.api import load,EarthSatellite,wgs84
from datetime import datetime,timezone

# ==========================================
# STARDANCE | EARTH EXPLORER
# ==========================================

print("Loading Earth texture...")

# Load your existing image at its original resolution
image = Image.open("earth.jpg").convert("RGB")
image.thumbnail((2048, 1024), Image.Resampling.LANCZOS)
texture = np.array(image)

height, width, _ = texture.shape
print(f"Texture: {width} x {height}")

# Create a smooth spherical grid
n_lat = 361
n_lon = 720

latitudes = np.linspace(-np.pi / 2, np.pi / 2, n_lat)
longitudes = np.linspace(-np.pi, np.pi, n_lon)

lon, lat = np.meshgrid(longitudes, latitudes)

# Convert latitude and longitude to 3D coordinates
x = np.cos(lat) * np.cos(lon)
y = np.cos(lat) * np.sin(lon)
z = np.sin(lat)

# Map the flat image onto the sphere
px = np.clip(
    ((lon + np.pi) / (2 * np.pi) * (width - 1)).astype(int),
    0, width - 1
)

py = np.clip(
    ((np.pi / 2 - lat) / np.pi * (height - 1)).astype(int),
    0, height - 1
)

rgb = texture[py, px]

# Give every globe vertex its actual image colour
vertex_colors = [
    f"rgb({r},{g},{b})"
    for r, g, b in rgb.reshape(-1, 3)
]

print("Building the 3D globe...")

# Construct two triangles for every grid cell
ids = np.arange(n_lat * n_lon).reshape(n_lat, n_lon)

a = ids[:-1, :-1].ravel()
b = ids[:-1, 1:].ravel()
c = ids[1:, 1:].ravel()
d = ids[1:, :-1].ravel()

i = np.concatenate([a, a])
j = np.concatenate([b, c])
k = np.concatenate([d, d])

# Solid, smoothly shaded Earth
earth = go.Mesh3d(
    x=x.ravel(),
    y=y.ravel(),
    z=z.ravel(),
    i=i,
    j=j,
    k=k,
    vertexcolor=vertex_colors,
    flatshading=False,
    opacity=1.0,
    lighting=dict(
        ambient=0.95,
        diffuse=0.05,
        specular=0.0,
        roughness=1.0
    ),
    showscale=False,
    hoverinfo="skip",
    name="Earth"
)

fig = go.Figure(data=[earth])
print("Downloading ISS Orbital Data...")
url="https.//celestrak.org/NORAD/elements/gp.php?CATNR=25544&FORMAT=TLE"


# Large viewing area and dark space
fig.update_layout(
    title=dict(
        text="STARDANCE | EARTH EXPLORER",
        x=0.5,
        font=dict(size=22, color="#E4F2FF")
    ),
    scene=dict(
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
        zaxis=dict(visible=False),
        aspectmode="data",
        bgcolor="black",
        camera=dict(
            eye=dict(x=1.35, y=1.35, z=1.0)
        ),
        dragmode="orbit"
    ),
    paper_bgcolor="black",
    font=dict(color="white"),
    margin=dict(l=0, r=0, t=65, b=0),
    height=850
)

# Open the interactive globe
fig.show(config={
    "scrollZoom": True,
    "displaylogo": False,
    "responsive": True
})

print("STARDANCE Earth Explorer is ready!")