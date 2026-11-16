"""Milestone B2: trade the battery through all of 2025 with four different price forecasts.

    python battery/backtest.py

For every day and every forecast:
  1. plan the day with the LP, using the FORECAST prices,
  2. count the money with the ACTUAL prices.

Outputs (in outputs/battery/):
  results.csv               one row per forecast: profit, capture rate, ...
  value_of_forecasting.csv  profit(OLS) - profit(naive), with a significance check
  profit_by_month.csv       profit per month per forecast
  daily_profit.csv   profit per day per forecast
  schedules.csv      the hourly charge/discharge/soc plan per forecast
"""

from pathlib import Path

import numpy as np
import pandas as pd

from battery_lp import Battery, optimise_day, settle

ROOT = Path(__file__).resolve().parent.parent
FORECASTS_FILE = ROOT / "outputs" / "forecasts_test.csv"
OUT_DIR = ROOT / "outputs" / "battery"

# column in forecasts_test.csv -> name shown in tables and charts
FORECASTS = {
    "price": "Perfect foresight (upper bound)",
    "ols_fc": "OLS, forecast weather (main)",
    "naive_d1": "Naive: same hour yesterday",
    "ols_noweather": "OLS, no weather",
}
PERFECT, MAIN, NAIVE = "price", "ols_fc", "naive_d1"


def load_data():
    return pd.read_csv(FORECASTS_FILE)


def run_backtest(data, battery=Battery(), forecasts=FORECASTS):
    """Plan every day on each forecast and settle at actual prices.

    Returns (daily, schedules):
      daily      DataFrame, index = date, one profit column per forecast (EUR)
      schedules  DataFrame, one row per hour, charge/discharge/soc columns per forecast
    """
    daily = {}
    schedules = data[["time_utc", "date", "hour", "price"]].copy()
    for column in forecasts:
        for part in ("charge", "discharge", "soc"):
            schedules[f"{part}_{column}"] = np.nan

    # A "day" is a Dutch local day: 24 hours, or 23 / 25 on the clock-change days.
    for date, day in data.groupby("date", sort=True):
        actual = day["price"].to_numpy()
        daily[date] = {}
        for column in forecasts:
            plan = optimise_day(day[column].to_numpy(), battery)
            daily[date][column] = settle(plan, actual, battery)
            for part in ("charge", "discharge", "soc"):
                schedules.loc[day.index, f"{part}_{column}"] = plan[part]

    daily = pd.DataFrame.from_dict(daily, orient="index")
    daily.index.name = "date"
    return daily, schedules


def hour_ranking_score(data, column):
    """How well does the forecast put the hours of a day in the right order? (1 = perfect)

    Per day: the rank correlation between forecast and actual prices. Then the average over days.
    The battery only needs to know WHICH hours are cheap and expensive, so this is what matters.
    """
    per_day = data.groupby("date").apply(
        lambda day: day[column].rank().corr(day["price"].rank()), include_groups=False)
    return per_day.mean()


def newey_west_t(x, lags=7):
    """t-statistic for "the mean of x is zero", robust to correlation between nearby days.

    Same idea as the Diebold-Mariano test in src/dm_test.py (Newey-West, 7 lags).
    """
    x = np.asarray(x, dtype=float)
    n = len(x)
    centred = x - x.mean()
    variance = centred @ centred / n
    for lag in range(1, lags + 1):
        weight = 1 - lag / (lags + 1)
        variance += 2 * weight * (centred[lag:] @ centred[:-lag]) / n
    return x.mean() / np.sqrt(variance / n)


def value_of_forecasting(daily, battery=Battery()):
    """Profit of the main OLS forecast minus profit of the naive forecast, with a few checks."""
    gain = daily[MAIN] - daily[NAIVE]
    return {
        "value_eur_per_mw_year": gain.sum() / battery.power_mw,
        "gain_vs_naive": gain.sum() / daily[NAIVE].sum(),
        "mean_gain_eur_per_day": gain.mean(),
        "newey_west_t": newey_west_t(gain),
        "share_days_better": (gain > 1e-6).mean(),
        "share_days_worse": (gain < -1e-6).mean(),
        "share_days_equal": (gain.abs() <= 1e-6).mean(),
    }


def summarise(data, daily, schedules, battery=Battery(), forecasts=FORECASTS):
    """One row per forecast with the key numbers."""
    rows = []
    perfect_profit = daily[PERFECT].sum()
    for column, name in forecasts.items():
        charge = schedules[f"charge_{column}"]
        discharge = schedules[f"discharge_{column}"]
        profit = daily[column].sum()
        rows.append({
            "forecast": name,
            "profit_eur": profit,
            "capture_rate": profit / perfect_profit,
            "profit_eur_per_mw_year": profit / battery.power_mw,
            "hour_ranking_score": hour_ranking_score(data, column),
            "full_cycles": discharge.sum() / battery.one_way_eff / battery.capacity_mwh,
            "avg_buy_price": (schedules["price"] * charge).sum() / charge.sum(),
            "avg_sell_price": (schedules["price"] * discharge).sum() / discharge.sum(),
            "days_with_loss": int((daily[column] < -1e-6).sum()),
            "hours_charge_and_discharge": int((np.minimum(charge, discharge) > 1e-6).sum()),
        })
    return pd.DataFrame(rows)


def main():
    battery = Battery()
    data = load_data()
    daily, schedules = run_backtest(data, battery)
    results = summarise(data, daily, schedules, battery)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results.round(4).to_csv(OUT_DIR / "results.csv", index=False)
    daily.round(2).to_csv(OUT_DIR / "daily_profit.csv")
    schedules.round(4).to_csv(OUT_DIR / "schedules.csv", index=False)

    print(f"Battery: {battery.power_mw:g} MW / {battery.capacity_mwh:g} MWh, "
          f"{battery.round_trip_eff:.0%} round trip, max {battery.max_cycles_per_day:g} cycle per day, "
          f"degradation {battery.degradation_eur_mwh:g} EUR/MWh")
    print(f"Days traded: {len(daily)} (2025)\n")

    table = results.copy()
    table["profit_eur"] = table["profit_eur"].map("{:,.0f}".format)
    table["capture_rate"] = table["capture_rate"].map("{:.1%}".format)
    table["hour_ranking_score"] = table["hour_ranking_score"].map("{:.2f}".format)
    table["full_cycles"] = table["full_cycles"].map("{:.0f}".format)
    table["avg_buy_price"] = table["avg_buy_price"].map("{:.1f}".format)
    table["avg_sell_price"] = table["avg_sell_price"].map("{:.1f}".format)
    print(table.drop(columns="profit_eur_per_mw_year").to_string(index=False))

    value = value_of_forecasting(daily, battery)
    pd.DataFrame([value]).round(4).to_csv(OUT_DIR / "value_of_forecasting.csv", index=False)
    print(f"\nValue of forecasting = profit(OLS, forecast weather) - profit(naive)")
    print(f"  = {value['value_eur_per_mw_year']:,.0f} EUR per MW per year  "
          f"({value['gain_vs_naive']:+.1%} vs naive, {value['mean_gain_eur_per_day']:.1f} EUR per day, "
          f"Newey-West t = {value['newey_west_t']:.2f})")
    print(f"  OLS earns more than naive on {value['share_days_better']:.0%} of days, "
          f"less on {value['share_days_worse']:.0%}, the same on {value['share_days_equal']:.0%}.")
    # In which months does the better forecast pay off?
    month = pd.to_datetime(daily.index).month
    by_month = daily.groupby(month).sum()
    by_month.index.name = "month"
    by_month["ols_minus_naive"] = by_month[MAIN] - by_month[NAIVE]
    by_month.round(2).to_csv(OUT_DIR / "profit_by_month.csv")
    print("\nProfit per month (EUR):")
    print(by_month.round(0).astype(int).to_string())

    print(f"\nSaved to {OUT_DIR.relative_to(ROOT)}: results.csv, value_of_forecasting.csv, "
          f"profit_by_month.csv, daily_profit.csv, schedules.csv")


if __name__ == "__main__":
    main()
