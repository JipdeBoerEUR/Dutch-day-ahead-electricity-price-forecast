"""Milestone 4: Model A, an OLS regression.

Run from the project folder (after src/benchmarks.py):

    python src/model_ols.py

Model (fitted ONCE on 2023-2024, then used unchanged on 2025):

    price = hour dummies + weekday dummies + month dummies
            + price yesterday + price last week
            + solar + wind + temperature + error

It prints the test-set MAE and RMSE next to the benchmarks and saves:

    outputs/forecasts_test.csv   gets a new column "ols"
    outputs/results.csv          results table for all models
    outputs/ols_summary.txt      full regression output
"""

from pathlib import Path

import pandas as pd
import statsmodels.formula.api as smf

from metrics import mae, rmse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "dataset.csv"
OUT_DIR = ROOT / "outputs"

# C(...) tells statsmodels to turn a column into dummy variables.
FORMULA = (
    "price ~ C(hour) + C(weekday) + C(month)"
    " + price_d1 + price_d7"
    " + solar_wm2 + wind100_ms + temp_c"
)
MAIN_VARIABLES = ["price_d1", "price_d7", "solar_wm2", "wind100_ms", "temp_c"]

# Honesty check: the same model WITHOUT weather. Our weather is what actually
# happened, not a forecast, so the full model is a bit too optimistic. A real
# forecast would land somewhere between this version and the full model.
FORMULA_NO_WEATHER = "price ~ C(hour) + C(weekday) + C(month) + price_d1 + price_d7"


def main():
    df = pd.read_csv(DATA)
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]

    # Fit on the training years only. HAC (Newey-West) standard errors, because
    # hourly price errors are correlated over time. This changes the t-values,
    # not the coefficients and not the forecasts.
    model = smf.ols(FORMULA, data=train).fit(cov_type="HAC", cov_kwds={"maxlags": 24})

    # Forecast 2025 with the coefficients from 2023-2024.
    forecast = model.predict(test)
    forecast_no_weather = smf.ols(FORMULA_NO_WEATHER, data=train).fit().predict(test)

    print("=" * 60)
    print("OLS MODEL")
    print("=" * 60)
    print(f"fitted on {len(train):,} train hours, {len(model.params)} coefficients")
    print(f"R-squared on train: {model.rsquared:.3f}")

    print("\nMAIN COEFFICIENTS (effect on price in EUR/MWh)")
    table = pd.DataFrame({
        "coef": model.params[MAIN_VARIABLES],
        "std_err": model.bse[MAIN_VARIABLES],
        "t": model.tvalues[MAIN_VARIABLES],
    })
    print(table.round(3).to_string())

    # Score everything on the same test set with the same metrics.
    candidates = {
        "Naive: same hour yesterday": test["price_d1"],
        "Naive: same hour last week": test["price_d7"],
        "OLS regression": forecast,
        "OLS without weather (check)": forecast_no_weather,
    }
    results = pd.DataFrame({
        name: {"MAE": mae(test["price"], f), "RMSE": rmse(test["price"], f)}
        for name, f in candidates.items()
    }).T
    best_naive = results.loc["Naive: same hour yesterday"]
    results["MAE_vs_yesterday_%"] = (results["MAE"] / best_naive["MAE"] - 1) * 100
    results["RMSE_vs_yesterday_%"] = (results["RMSE"] / best_naive["RMSE"] - 1) * 100

    print("\nTEST SET 2025 (EUR/MWh; negative % = better than 'yesterday')")
    print(results.round(2).to_string())

    print(f"\nAverage OLS error (forecast - actual): {(forecast - test['price']).mean():+.2f} EUR/MWh")

    in_sample = model.predict(train)
    print(f"\nFor context, OLS on its own training data: "
          f"MAE {mae(train['price'], in_sample):.2f}   RMSE {rmse(train['price'], in_sample):.2f}")

    # Save.
    forecasts = pd.read_csv(OUT_DIR / "forecasts_test.csv")
    forecasts["ols"] = forecast.to_numpy()
    forecasts.to_csv(OUT_DIR / "forecasts_test.csv", index=False)
    results.round(2).to_csv(OUT_DIR / "results.csv", index_label="model")
    (OUT_DIR / "ols_summary.txt").write_text(model.summary().as_text(), encoding="utf-8")
    print("\nSaved: outputs/forecasts_test.csv (column 'ols'), outputs/results.csv, outputs/ols_summary.txt")


if __name__ == "__main__":
    main()
