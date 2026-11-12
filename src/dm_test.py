"""Diebold-Mariano test: is a forecast SIGNIFICANTLY better than the naive one?

Run from the project folder (after src/model_ols.py):

    python src/dm_test.py

A lower MAE on one test year could be luck. The Diebold-Mariano (DM) test
checks this. For each model, against "same hour yesterday":

    1. loss            = absolute error of each hourly forecast
    2. loss difference = loss of naive - loss of model   (positive = model is better)
    3. average the difference per delivery day  -> one number per day (365 in 2025)
    4. test whether the mean of those daily numbers is zero

Step 3 matters: the 24 hours of one day are forecast at the same moment and
their errors move together, so they are not 24 independent observations.
Step 4 uses Newey-West (HAC) standard errors, because good and bad days also
come in runs.

It adds the columns DM_stat and DM_p_value to outputs/results.csv.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"

BENCHMARK = "naive_d1"          # same hour yesterday
HAC_LAGS = 7                    # one week of daily values

# Results-table name -> column in outputs/forecasts_test.csv
MODELS = {
    "Naive: same hour last week": "naive_d7",
    "OLS, forecast weather": "ols_fc",
    "OLS, actual weather (upper bound)": "ols_actual",
    "OLS, no weather": "ols_noweather",
}


def daily_loss_difference(df, column):
    """Per day: mean absolute error of the benchmark minus that of the model."""
    loss_benchmark = (df["price"] - df[BENCHMARK]).abs()
    loss_model = (df["price"] - df[column]).abs()
    return (loss_benchmark - loss_model).groupby(df["date"]).mean()


def dm_test(daily_difference, lags=HAC_LAGS):
    """DM statistic and two-sided p-value.

    Regressing the daily differences on a constant gives their mean. With HAC
    standard errors, the t-value of that constant is the DM statistic.
    """
    constant = np.ones(len(daily_difference))
    fit = sm.OLS(daily_difference.to_numpy(), constant).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags}
    )
    return float(fit.tvalues[0]), float(fit.pvalues[0])


def main():
    df = pd.read_csv(OUT_DIR / "forecasts_test.csv")
    results = pd.read_csv(OUT_DIR / "results.csv").set_index("model")
    results = results.drop(columns=["DM_stat", "DM_p_value"], errors="ignore")

    print("=" * 60)
    print("DIEBOLD-MARIANO TEST vs 'same hour yesterday', 2025")
    print("=" * 60)
    print(f"loss: absolute error, averaged per day; HAC standard errors with {HAC_LAGS} lags")
    print("H0: the model and the naive forecast are equally accurate")
    print("positive DM statistic = the model is better\n")

    rows = {}
    for name, column in MODELS.items():
        d = daily_loss_difference(df, column)
        stat, p_value = dm_test(d)
        rows[name] = {"DM_stat": stat, "DM_p_value": p_value}
        print(f"{name:36s} days {len(d)}   mean daily gain {d.mean():6.2f} EUR/MWh"
              f"   days better {100 * (d > 0).mean():4.1f}%"
              f"   DM {stat:6.2f}   p {p_value:.2g}")

    # Robustness: does the answer depend on the number of HAC lags?
    print("\nROBUSTNESS: DM statistic with other HAC lag choices")
    for name, column in MODELS.items():
        d = daily_loss_difference(df, column)
        stats = "   ".join(f"{lags} lags: {dm_test(d, lags)[0]:6.2f}" for lags in (0, 7, 14, 28))
        print(f"{name:36s} {stats}")

    results = results.join(pd.DataFrame(rows).T)
    # Round the normal columns; keep p-values in scientific notation (they can be tiny).
    normal = [c for c in results.columns if c != "DM_p_value"]
    results[normal] = results[normal].round(2)
    results["DM_p_value"] = results["DM_p_value"].map(lambda p: "" if pd.isna(p) else f"{p:.2e}")
    results.to_csv(OUT_DIR / "results.csv", index_label="model")
    print("\nSaved: outputs/results.csv (new columns DM_stat, DM_p_value)")


if __name__ == "__main__":
    main()
