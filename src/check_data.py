"""Milestone 1: check the downloaded data before we build anything on it.

Run from the project folder (after data/download_data.py):

    python src/check_data.py

It prints a short data-quality report and saves one overview chart to
outputs/figures/01_data_check.png.
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt
import pandas as pd

TZ = "Europe/Amsterdam"
ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
FIG_DIR = ROOT / "outputs" / "figures"


def load(name):
    df = pd.read_csv(RAW_DIR / name)
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    return df.set_index("time_utc")


def expected_hours():
    """Every hour from 2023-01-01 00:00 to 2025-12-31 23:00, Dutch local time."""
    start = pd.Timestamp("2023-01-01", tz=TZ).tz_convert("UTC")
    end = pd.Timestamp("2026-01-01", tz=TZ).tz_convert("UTC")
    return pd.date_range(start, end, freq="1h", inclusive="left")


def completeness(df, label):
    """Are all hours there, exactly once, with no empty values?"""
    hours = expected_hours()
    missing = hours.difference(df.index)
    print(f"\n{label}")
    print(f"  rows: {len(df):,}   expected: {len(hours):,}")
    print(f"  first: {df.index.min()}   last: {df.index.max()}")
    print(f"  missing hours: {len(missing)}   duplicate hours: {df.index.duplicated().sum()}")
    print(f"  empty values per column: {df.isna().sum().to_dict()}")
    if len(missing):
        print(f"  first missing hours: {list(missing[:5])}")


def main():
    prices = load("prices_nl_hourly.csv")
    raw = load("prices_nl_raw.csv")
    weather = load("weather_nl_hourly.csv")

    print("=" * 60)
    print("DATA CHECK")
    print("=" * 60)

    completeness(prices, "PRICES (hourly)")
    completeness(weather, "WEATHER (hourly)")

    # When did the market switch from hourly to 15-minute prices?
    step = raw.index.to_series().diff()
    quarter = step[step == pd.Timedelta(minutes=15)]
    print("\nPRICE RESOLUTION")
    print(f"  raw rows: {len(raw):,}")
    print(f"  time steps found: {step.value_counts().to_dict()}")
    if len(quarter):
        print(f"  first 15-minute price: {quarter.index.min().tz_convert(TZ)}")

    # Yearly summary of prices (using the Dutch local year).
    local = prices.tz_convert(TZ)
    p = local["price_eur_mwh"]
    summary = p.groupby(local.index.year).agg(
        mean="mean", median="median", std="std", min="min", max="max"
    )
    summary["neg_hours_%"] = (p < 0).groupby(local.index.year).mean() * 100
    print("\nPRICES PER YEAR (EUR/MWh)")
    print(summary.round(1).to_string())

    print("\nWEATHER SUMMARY (average of 5 locations)")
    print(weather.describe().loc[["mean", "min", "max"]].round(1).to_string())

    # Does the price react to weather the way we expect? (simple correlations)
    both = prices.join(weather, how="inner")
    print("\nCORRELATION WITH PRICE (same hour)")
    print(both.corr()["price_eur_mwh"].drop("price_eur_mwh").round(2).to_string())

    # One overview chart: daily average price, and the average price per hour.
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    p.resample("1D").mean().plot(ax=axes[0], color="#1f4e79", linewidth=0.8)
    axes[0].axvline(pd.Timestamp("2025-01-01", tz=TZ), color="grey", linestyle="--")
    axes[0].set_title("Daily average day-ahead price, NL")
    axes[0].set_ylabel("EUR/MWh")
    axes[0].set_xlabel("")

    by_hour = p.groupby([local.index.year, local.index.hour]).mean().unstack(0)
    by_hour.plot(ax=axes[1], linewidth=1.5)
    axes[1].set_title("Average price by hour of day")
    axes[1].set_xlabel("Hour (Dutch local time)")
    axes[1].set_ylabel("EUR/MWh")
    axes[1].legend(title="Year")

    fig.tight_layout()
    out = FIG_DIR / "01_data_check.png"
    fig.savefig(out, dpi=150)
    print(f"\nChart saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
