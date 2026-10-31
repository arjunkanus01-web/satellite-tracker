# 🌍 TERRA — Live Earth & ISS Tracker

Hi! This is TERRA, a project I've been working on because I'm really interested in astronomy, space and programming.

I've always found it fascinating that the International Space Station travels around Earth at incredible speeds. So I thought, why not try building something that actually tracks it?

That's how TERRA started!
https://satellite-tracker-32vz.onrender.com -Demo link

It's a Python-based project where I created a 3D model of Earth and added ISS tracking to it. You can see where the ISS is, where it's going next and even check when it might pass over a location.

## 🚀 What can TERRA do?

Here are some of the main things I've added:

- A 3D Earth with a realistic texture.
- Atmospheric layers and stars to make the scene look more like space.
- Live ISS position updates every two seconds.
- A predicted path showing where the ISS will travel next.
- The ability to enter your own latitude and longitude.
- Predictions of upcoming ISS passes over the next 24 hours.
- Rise, culmination (highest point) and set times.
- Azimuth and elevation calculations.
- Automatic downloading and saving of orbital data.
- A backup system so the tracker can still use previously saved data if CelesTrak is unavailable.

## 🛠️ Technologies I used

| Technology | What it does in my project |
|---|---|
| Python | The main language I used to build TERRA |
| Skyfield | Calculates satellite positions and passes |
| SGP4 | Predicts the ISS orbit |
| Plotly | Creates the interactive 3D Earth |
| Dash | Turns the project into a web application |
| NumPy | Handles mathematical calculations |
| Pillow | Loads and processes the Earth texture |
| CelesTrak | Provides the ISS orbital data |

## 🛰️ How does the tracking actually work?

This is probably the most interesting part of the project!

### 1. Getting the ISS data

First, TERRA downloads something called TLE (Two-Line Element) data from CelesTrak.

It uses the NORAD catalogue number `25544` to identify the ISS.

The TLE contains the orbital information needed to calculate where the satellite is.

### 2. Calculating its position

I used the Skyfield library, which uses the SGP4 orbital propagation model.

Basically, it takes the TLE data and calculates where the ISS should be at a particular time.

This is how TERRA gets its current and predicted positions.

### 3. Showing it on Earth

Once the position is calculated, Skyfield helps convert it into latitude and longitude using the WGS84 coordinate system.

I then convert those coordinates into 3D coordinates so that the ISS can be displayed on the Earth model.

### 4. Showing where it will go next

TERRA doesn't just show the current position.

It calculates several future positions over approximately 95 minutes and connects them to create a predicted ground track.

This shows the locations directly below the ISS as it travels around Earth.

### 5. Finding upcoming ISS passes

Another feature I wanted to add was the ability to check when the ISS might pass over a particular location.

You can enter your latitude and longitude, and TERRA calculates upcoming passes over the next 24 hours.

It gives three main events:

- **Rise:** When the ISS crosses above the horizon.
- **Culmination:** When it reaches its highest point in the sky.
- **Set:** When it goes below the horizon.

It also calculates the azimuth and elevation at each event.

These are geometric horizon predictions, so actual visibility can depend on buildings, mountains, weather and sunlight.

## 💾 What if CelesTrak stops responding?

I didn't want the whole tracker to stop working just because an external website was temporarily unavailable.

So I added a TLE caching system.

Here's how it works:

- TERRA saves the latest valid orbital data in a file called `iss.tle`.
- It reuses that data for up to six hours by default.
- When the saved data becomes old, it tries to download a newer version.
- If the download fails, it attempts to use the previously saved data.

The ISS position updates every two seconds, but TLE data isn't downloaded every two seconds. That would create unnecessary requests.

I also made the Python server handle the TLE download instead of the browser. This avoids browser-side CORS issues when requesting the orbital data.

## 💻 Want to run TERRA yourself?

You can download the project and run it on your own computer.

### What you need

- Python 3.10 or newer.
- An internet connection for the initial orbital data download.

### Step 1 — Clone the repository

```bash
git clone https://github.com/arjunkanus01-web/satellite-tracker.git
cd satellite-tracker
```

### Step 2 — Install the libraries

```bash
python -m pip install -r requirements.txt
```

### Step 3 — Start TERRA

```bash
python app.py
```

Now open:

```text
http://127.0.0.1:8050
```

And you're ready to explore TERRA!

**Important:** Keep `earth.jpg` in the same folder as `app.py`.

## 🌐 How is TERRA hosted?

I use Render to make TERRA accessible online.

Since this project uses Python and Dash, it needs a hosting service that can actually run a Python application. GitHub Pages alone cannot do that.

These are the commands used for deployment:

**Build command**

```bash
pip install -r requirements.txt
```

**Start command**

```bash
python app.py
```

The application uses the port provided by the hosting service.

For the saved TLE data to survive server restarts, persistent storage is needed if the hosting provider supports it.

## 📁 Project structure

```text
satellite-tracker/
│
├── app.py
├── requirements.txt
├── README.md
├── earth.jpg
└── iss.tle
```

The `iss.tle` file is automatically created after the first successful download.

## ⚠️ Things I still want to improve

TERRA is a project I'm still developing, so there are some limitations:

- The accuracy of predictions depends on how recent the TLE data is.
- A predicted pass doesn't guarantee that the ISS will be visible to the naked eye.
- Buildings, mountains and weather aren't included in the pass calculations.
- Some hosting services may delete cached files when the server restarts.

There is still plenty of room to improve!

## 🌌 Why I built TERRA

I didn't want to make just another Python program that prints satellite coordinates.

I wanted to combine astronomy, mathematics, programming and 3D visualisation into one project.

Building TERRA has helped me understand more about orbital tracking, coordinate systems, satellite data and how different Python libraries can work together.

And this is only the beginning. I have many more ideas I'd like to try with TERRA!
