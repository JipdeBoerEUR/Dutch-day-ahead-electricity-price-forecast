"""Milestone 2: merge prices + weather and build the model features.

Run from the project folder (after data/download_data.py):

    python src/build_dataset.py

It writes data/processed/dataset.csv with one row per hour:

    price       the price we want to forecast (EUR/MWh)
    price_d1    price in the same clock hour yesterday
    price_d7    price in the same clock hour one week ago
    solar_wm2, wind100_ms, temp_c   weather in that hour (proxy for the forecast)
    hour, weekday, month            calendar info in Dutch local time
    split       "train" (2023-2024) or "test" (2025)
"""

from pathlib import Path

import pandas as pd

TZ = "Europe/Amsterdam"
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"


def load(name):
    df = pd.read_csv(RAW_DIR / name)
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    return df


def lagged_price(df, days):
    """Price in the same CLOCK hour, `days` days earlier (Dutch local time).

    We look the value up by clock time instead of shifting 24 rows, because
    two days per year do not have 24 hours:
      - October clock change (25 hours): 02:00 happens twice -> use the average.
      - March clock change (23 hours): 02:00 does not exist -> fill it in
        between 01:00 and 03:00.
    """
    clock = df["time_local"].dt.tz_localize(None)        # e.g. 2025-03-30 14:00
    lookup = df.groupby(clock)["price"].mean()            # one price per clock hour
    all_hours = pd.date_range(lookup.index.min(), lookup.index.max(), freq="1h")
    lookup = lookup.reindex(all_hours).interpolate()      # fills the skipped March hour
    return (clock - pd.Timedelta(days=days)).map(lookup)


def main():
    prices = load("prices_nl_hourly.csv").rename(columns={"price_eur_mwh": "price"})
    weather = load("weather_nl_hourly.csv")

    # 1. Merge: one row per hour with price + weather.
    df = prices.merge(weather, on="time_utc", how="inner", validate="one_to_one")
    df = df.sort_values("time_utc").reset_index(drop=True)

    # 2. Calendar features in Dutch local time (the market follows local time).
    df["time_local"] = df["time_utc"].dt.tz_convert(TZ)
    df["date"] = df["time_local"].dt.date
    df["year"] = df["time_local"].dt.year
    df["month"] = df["time_local"].dt.month
    df["weekday"] = df["time_local"].dt.dayofweek          # 0 = Monday ... 6 = Sunday
    df["hour"] = df["time_local"].dt.hour

    # 3. Lagged prices. Both are known before the auction for day D closes
    #    (12:00 on D-1): yesterday's prices were published the day before that.
    df["price_d1"] = lagged_price(df, days=1)
    df["price_d7"] = lagged_price(df, days=7)

    # 4. Drop the first 7 days: they have no price from a week earlier.
    before = len(df)
    df = df.dropna(subset=["price_d1", "price_d7"]).reset_index(drop=True)
    dropped = before - len(df)

    # 5. Train / test split by calendar year.
    df["split"] = df["year"].map(lambda y: "test" if y == 2025 else "train")

    columns = [
        "time_utc", "date", "year", "month", "weekday", "hour",
        "price", "price_d1", "price_d7",
        "solar_wm2", "wind100_ms", "temp_c", "split",
    ]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "dataset.csv"
    df[columns].to_csv(out, index=False)

    # ---- Report -----------------------------------------------------------
    print("=" * 60)
    print("DATASET BUILT")
    print("=" * 60)
    print(f"rows: {len(df):,}   (dropped first {dropped} hours = 7 days)")
    print(f"empty values: {int(df[columns].isna().sum().sum())}")

    print("\nTRAIN / TEST")
    for name, part in df.groupby("split", sort=False):
        print(f"  {name:5s}  {part['date'].min()} to {part['date'].max()}   {len(part):,} hours")

    hours_per_day = df.groupby("date").size().value_counts().sort_index()
    print(f"\nHOURS PER DAY (23 and 25 = clock-change days): {hours_per_day.to_dict()}")

    # Check the lag on a clock-change day: 30 March 2025 (23 hours).
    show = df[df["date"].astype(str) == "2025-03-31"].head(4)
    prev = df[df["date"].astype(str) == "2025-03-30"].head(3)
    print("\nLAG CHECK around the March 2025 clock change")
    print("  prices on 30 March (hour 2 does not exist):")
    print(prev[["hour", "price"]].to_string(index=False))
    print("  31 March: price_d1 must equal the 30 March price in the same hour")
    print(show[["hour", "price", "price_d1"]].round(2).to_string(index=False))

    print("\nCORRELATION WITH PRICE (train only)")
    train = df[df["split"] == "train"]
    features = ["price_d1", "price_d7", "solar_wm2", "wind100_ms", "temp_c"]
    print(train[["price"] + features].corr()["price"].drop("price").round(2).to_string())

    print(f"\nSaved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
