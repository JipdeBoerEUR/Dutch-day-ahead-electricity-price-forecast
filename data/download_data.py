"""Download the raw data for the project (prices + weather).

Run from the project folder:

    python data/download_data.py

It writes three CSV files to data/raw/ (this folder is NOT committed to git):

    prices_nl_raw.csv      prices exactly as published (hourly, 15-min from Oct 2025)
    prices_nl_hourly.csv   the same prices as one value per hour
    weather_nl_hourly.csv  solar, wind and temperature, averaged over 5 Dutch locations

All timestamps are in UTC and mark the START of the hour.
"""

from pathlib import Path
import time

import pandas as pd
import requests

# ---- Settings -------------------------------------------------------------

TZ = "Europe/Amsterdam"          # the market runs on Dutch local time
START_LOCAL = "2023-01-01"       # first delivery day (included)
END_LOCAL = "2026-01-01"         # day after the last delivery day (excluded)
YEARS = (2023, 2024, 2025)

PRICE_URL = "https://api.energy-charts.info/price"            # Fraunhofer ISE
WEATHER_URL = "https://archive-api.open-meteo.com/v1/archive"  # Open-Meteo

# A few locations spread over the country: (latitude, longitude)
LOCATIONS = {
    "De Bilt (centre)": (52.10, 5.18),
    "Groningen (north)": (53.22, 6.57),
    "Eindhoven (south)": (51.44, 5.48),
    "Vlissingen (south-west coast)": (51.44, 3.57),
    "Den Helder (north-west coast)": (52.96, 4.76),
}

WEATHER_VARS = {
    "shortwave_radiation": "solar_wm2",   # W/m2, drives solar power
    "wind_speed_100m": "wind100_ms",      # m/s at 100 m, drives wind power
    "temperature_2m": "temp_c",           # deg C, drives demand
}

RAW_DIR = Path(__file__).parent / "raw"


# ---- Helpers --------------------------------------------------------------

def get_json(url, params, tries=4):
    """GET a URL and return the JSON. Retries a few times if the server is busy."""
    for attempt in range(1, tries + 1):
        try:
            response = requests.get(url, params=params, timeout=120)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as error:
            if attempt == tries:
                raise
            wait = 10 * attempt
            print(f"  request failed ({error}); retrying in {wait}s")
            time.sleep(wait)


def keep_study_period(df):
    """Keep only rows inside 2023-01-01 .. 2025-12-31 in Dutch local time."""
    start = pd.Timestamp(START_LOCAL, tz=TZ).tz_convert("UTC")
    end = pd.Timestamp(END_LOCAL, tz=TZ).tz_convert("UTC")
    inside = (df["time_utc"] >= start) & (df["time_utc"] < end)
    return df[inside].reset_index(drop=True)


# ---- Prices ---------------------------------------------------------------

def download_prices():
    """Dutch day-ahead prices in EUR/MWh from energy-charts.info."""
    parts = []
    for year in YEARS:
        print(f"  prices {year}")
        # Ask one extra day on each side, so no local-time hour is cut off.
        params = {"bzn": "NL", "start": f"{year - 1}-12-31", "end": f"{year + 1}-01-01"}
        data = get_json(PRICE_URL, params)
        parts.append(pd.DataFrame({
            "time_utc": pd.to_datetime(data["unix_seconds"], unit="s", utc=True),
            "price_eur_mwh": data["price"],
        }))
        time.sleep(1)

    raw = pd.concat(parts).drop_duplicates("time_utc").sort_values("time_utc")
    raw = keep_study_period(raw)

    # From 1 Oct 2025 the market clears every 15 minutes instead of every hour.
    # The hourly price is then the average of the four quarter-hour prices.
    hourly = (
        raw.set_index("time_utc")["price_eur_mwh"]
        .resample("1h").mean()
        .reset_index()
    )
    return raw, hourly


# ---- Weather --------------------------------------------------------------

def download_weather():
    """Hourly weather (reanalysis = what actually happened), averaged over locations."""
    per_location = []
    for name, (lat, lon) in LOCATIONS.items():
        print(f"  weather {name}")
        params = {
            "latitude": lat,
            "longitude": lon,
            "start_date": "2022-12-31",   # one extra day on each side
            "end_date": "2026-01-01",
            "hourly": ",".join(WEATHER_VARS),
            "timezone": "UTC",
            "wind_speed_unit": "ms",
        }
        data = get_json(WEATHER_URL, params)["hourly"]
        df = pd.DataFrame(data).rename(columns=WEATHER_VARS)
        df["time_utc"] = pd.to_datetime(df.pop("time"), utc=True)
        per_location.append(df.set_index("time_utc"))
        time.sleep(1)

    # Simple average over the locations, hour by hour.
    average = sum(per_location) / len(per_location)
    return keep_study_period(average.reset_index())


# ---- Main -----------------------------------------------------------------

def main():
    RAW_DIR.mkdir(exist_ok=True)

    print("Downloading prices (energy-charts.info, bidding zone NL)")
    raw, hourly = download_prices()
    raw.to_csv(RAW_DIR / "prices_nl_raw.csv", index=False)
    hourly.to_csv(RAW_DIR / "prices_nl_hourly.csv", index=False)
    print(f"  saved {len(raw):,} raw rows -> {len(hourly):,} hourly rows")

    print("Downloading weather (Open-Meteo archive)")
    weather = download_weather()
    weather.to_csv(RAW_DIR / "weather_nl_hourly.csv", index=False)
    print(f"  saved {len(weather):,} hourly rows")

    print("Done. Next: python src/check_data.py")


if __name__ == "__main__":
    main()
