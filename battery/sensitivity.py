"""Milestone B3: does the answer change with a different battery?

    python battery/sensitivity.py

Only two things are changed, one at a time. Everything else stays as in the base case.
  - Duration:    1 h / 2 h / 4 h   (capacity 1 / 2 / 4 MWh at 1 MW)
  - Degradation: 0 / 10 / 20 EUR per MWh sold

Output: outputs/battery/sensitivity.csv (one row per case and forecast).
"""

import pandas as pd

from backtest import FORECASTS, MAIN, NAIVE, OUT_DIR, PERFECT, ROOT, load_data, run_backtest
from battery_lp import Battery

BASE = Battery()                               # 1 MW, 2 h, degradation 10
DURATIONS_H = [1.0, 2.0, 4.0]
DEGRADATIONS_EUR_MWH = [0.0, 10.0, 20.0]


def run_case(data, battery):
    """Run 2025 for one battery. Returns one row per forecast."""
    daily, schedules = run_backtest(data, battery)
    profit = daily.sum()
    rows = []
    for column, name in FORECASTS.items():
        sold = schedules[f"discharge_{column}"].sum()
        rows.append({
            "duration_h": battery.duration_h,
            "degradation_eur_mwh": battery.degradation_eur_mwh,
            "forecast": name,
            "profit_eur": profit[column],
            "capture_rate": profit[column] / profit[PERFECT],
            "gain_vs_naive_eur": profit[column] - profit[NAIVE],
            "full_cycles": sold / battery.one_way_eff / battery.capacity_mwh,
            "days_with_loss": int((daily[column] < -1e-6).sum()),
        })
    return rows


def print_block(results, vary, title):
    """One line per case: profit per forecast, capture rates and the value of forecasting."""
    names = {column: name for column, name in FORECASTS.items()}
    print(f"\n{title}")
    print(f"{vary:>20} | {'perfect':>8} {'OLS':>8} {'naive':>8} {'OLS no w.':>9} | "
          f"{'OLS capt.':>9} {'naive capt.':>11} | {'value of forecasting':>21}")
    for value, case in results.groupby(vary):
        by_forecast = case.set_index("forecast")
        profit = by_forecast["profit_eur"]
        capture = by_forecast["capture_rate"]
        gain = profit[names[MAIN]] - profit[names[NAIVE]]
        print(f"{value:>20g} | {profit[names[PERFECT]]:>8,.0f} {profit[names[MAIN]]:>8,.0f} "
              f"{profit[names[NAIVE]]:>8,.0f} {profit[names['ols_noweather']]:>9,.0f} | "
              f"{capture[names[MAIN]]:>9.1%} {capture[names[NAIVE]]:>11.1%} | "
              f"{gain:>9,.0f} EUR ({gain / profit[names[NAIVE]]:+.1%})")


def main():
    data = load_data()

    # The base case (2 h, 10 EUR/MWh) is in both lists. Run each different battery once.
    cases = {}
    for duration in DURATIONS_H:
        cases[(duration, BASE.degradation_eur_mwh)] = Battery(duration_h=duration)
    for degradation in DEGRADATIONS_EUR_MWH:
        cases[(BASE.duration_h, degradation)] = Battery(degradation_eur_mwh=degradation)

    rows = []
    for battery in cases.values():
        rows.extend(run_case(data, battery))
    results = pd.DataFrame(rows).sort_values(["duration_h", "degradation_eur_mwh"], kind="stable")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    results.round(4).to_csv(OUT_DIR / "sensitivity.csv", index=False)

    print("Profit in 2025 (EUR per MW per year). Value of forecasting = OLS (forecast weather) - naive.")
    print_block(results[results["degradation_eur_mwh"] == BASE.degradation_eur_mwh], "duration_h",
                f"A. Battery duration (degradation {BASE.degradation_eur_mwh:g} EUR/MWh)")
    print_block(results[results["duration_h"] == BASE.duration_h], "degradation_eur_mwh",
                f"B. Degradation cost (duration {BASE.duration_h:g} h)")
    print(f"\nSaved to {(OUT_DIR / 'sensitivity.csv').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
