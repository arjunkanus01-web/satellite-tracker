from urllib.request import urlopen
from datetime import timedelta, timezone

from skyfield.api import load, wgs84, EarthSatellite


URL = (
    "https://celestrak.org/NORAD/elements/"
    "gp.php?GROUP=visual&FORMAT=tle"
)


def main():
    print("STARDANCE SATELLITE TRACKER")
    print("Location: Trivandrum")
    print("Downloading satellite data...", flush=True)

    try:
        # Download satellite catalogue
        with urlopen(URL, timeout=30) as response:
            tle_text = response.read().decode("utf-8")

        lines = [
            line.strip()
            for line in tle_text.splitlines()
            if line.strip()
        ]

        ts = load.timescale()
        satellites = []

        # Read the three-line TLE records
        for i in range(0, len(lines) - 2, 3):
            name, line1, line2 = lines[i:i + 3]

            if line1.startswith("1 ") and line2.startswith("2 "):
                satellites.append(
                    EarthSatellite(line1, line2, name, ts)
                )

        print("Satellites loaded:", len(satellites))

        if not satellites:
            print("No satellites were loaded. Check the downloaded data.")
            return

        # Observer: Trivandrum
        observer = wgs84.latlon(
            latitude_degrees=8.5241,
            longitude_degrees=76.9366
        )

        # Current and future times
        now = ts.now()
        future_datetime = (
            now.utc_datetime() + timedelta(minutes=10)
        ).replace(tzinfo=timezone.utc)
        future = ts.from_datetime(future_datetime)

        # Load the solar-system ephemeris
        print("Loading Sun position data...", flush=True)
        eph = load("de421.bsp")

        # Sun altitude as seen from Trivandrum
        sun_position = (
            (eph["earth"] + observer)
            .at(now)
            .observe(eph["sun"])
            .apparent()
        )

        sun_altitude = sun_position.altaz()[0].degrees

        if sun_altitude >= 0:
            sky_status = "DAYLIGHT"
        elif sun_altitude > -6:
            sky_status = "CIVIL TWILIGHT"
        elif sun_altitude > -12:
            sky_status = "NAUTICAL TWILIGHT"
        elif sun_altitude > -18:
            sky_status = "ASTRONOMICAL TWILIGHT"
        else:
            sky_status = "DARK SKY"

        print(f"Sun altitude: {sun_altitude:.1f} degrees")
        print("Sky condition:", sky_status)

        above_horizon = []

        # Calculate each satellite separately
        for satellite in satellites:
            position = (satellite - observer).at(now)
            elevation, azimuth, distance = position.altaz()

            future_position = (satellite - observer).at(future)
            future_elevation, future_azimuth, future_distance = (
                future_position.altaz()
            )

            # Recalculate for every satellite
            elevation_change = (
                future_elevation.degrees - elevation.degrees
            )

            if elevation_change > 0.1:
                movement = "RISING"
            elif elevation_change < -0.1:
                movement = "SETTING"
            else:
                movement = "STEADY"

            sat_position = satellite.at(now)
            sunlit = sat_position.is_sunlit(eph)

            if not sunlit:
                visibility = "IN EARTH SHADOW"
            elif sun_altitude >= 0:
                visibility = "DAYLIGHT - UNLIKELY"
            elif sun_altitude > -6:
                visibility = "TWILIGHT - UNCERTAIN"
            elif elevation.degrees < 10:
                visibility = "LOW - HARD TO SEE"
            elif elevation.degrees >= 30:
                visibility = "GOOD GEOMETRY - CHECK BRIGHTNESS"
            else:
                visibility = "POSSIBLE - CHECK BRIGHTNESS"

            if elevation.degrees > 0:
                above_horizon.append(
                    (
                        satellite.name,
                        elevation.degrees,
                        azimuth.degrees,
                        sunlit,
                        visibility,
                        movement,
                        elevation_change
                    )
                )

        # Highest elevation first
        above_horizon.sort(
            key=lambda item: item[1],
            reverse=True
        )

        print(
            "\nSatellites above the horizon:",
            len(above_horizon)
        )

        for (
            name,
            elevation,
            azimuth,
            sunlit,
            visibility,
            movement,
            elevation_change
        ) in above_horizon[:30]:
            print(
                f"{name} | Elevation: {elevation:.1f}° | "
                f"Azimuth: {azimuth:.1f}° | "
                f"Sunlit: {sunlit} | Visibility: {visibility} | "
                f"Movement: {movement} | "
                f"Change in 10 min: {elevation_change:+.1f}°"
            )

        print("\nSTARDANCE check complete.")

    except Exception as error:
        print(
            "STARDANCE failed:",
            type(error).__name__,
            error
        )


if __name__ == "__main__":
    main()