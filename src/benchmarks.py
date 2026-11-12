"""Milestone 3: the two naive benchmarks.

Run from the project folder (after src/build_dataset.py):

    python src/benchmarks.py

Benchmark 1 "yesterday":  forecast = price in the same hour yesterday
Benchmark 2 "last week":  forecast = price in the same hour one week ago

A naive benchmark needs no fitting. It is the bar any real model must beat.
The script prints MAE and RMSE on the 2025 test set and saves:

    outputs/forecasts_test.csv      actual price + both benchmark forecasts
    outputs/results_benchmarks.csv  the results table
"""

from pathlib import Path

import pandas as pd

from metrics import mae, rmse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "dataset.csv"
OUT_DIR = ROOT / "outputs"

BENCHMARKS = {
    "Naive: same hour yesterday": "price_d1",
    "Naive: same hour last week": "price_d7",
}


def main():
    df = pd.read_csv(DATA)
    test = df[df["split"] == "test"]

    # The forecasts already exist as columns: the lagged prices from milestone 2.
    rows = []
    for name, column in BENCHMARKS.items():
        rows.append({
            "model": name,
            "MAE": mae(test["price"], test[column]),
            "RMSE": rmse(test["price"], test[column]),
        })
    results = pd.DataFrame(rows).set_index("model")

    print("=" * 60)
    print("BENCHMARKS on the 2025 test set (EUR/MWh)")
    print("=" * 60)
    print(f"test hours: {len(test):,}   average price in 2025: {test['price'].mean():.1f}")
    print()
    print(results.round(2).to_string())

    # Same numbers on the training years, only to see if 2025 is harder or easier.
    train = df[df["split"] == "train"]
    print("\nFor context, the same benchmarks on 2023-2024:")
    for name, column in BENCHMARKS.items():
        print(f"  {name:28s} MAE {mae(train['price'], train[column]):.2f}"
              f"   RMSE {rmse(train['price'], train[column]):.2f}")

    OUT_DIR.mkdir(exist_ok=True)
    forecasts = test[["time_utc", "date", "hour", "price"]].copy()
    forecasts["naive_d1"] = test["price_d1"]
    forecasts["naive_d7"] = test["price_d7"]
    forecasts.to_csv(OUT_DIR / "forecasts_test.csv", index=False)
    results.round(2).to_csv(OUT_DIR / "results_benchmarks.csv")
    print("\nSaved: outputs/forecasts_test.csv, outputs/results_benchmarks.csv")


if __name__ == "__main__":
    main()
