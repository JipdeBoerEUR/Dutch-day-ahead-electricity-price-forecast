"""Milestone 4: Model A, an OLS regression.

Run from the project folder (after src/benchmarks.py):

    python src/model_ols.py

Model (fitted ONCE on 2023-2024, then used unchanged on 2025):

    price = hour dummies + weekday dummies + month dummies
            + price yesterday + price last week
            + solar + wind + temperature + error

The model is scored on 2025 in three ways:

    OLS, forecast weather   MAIN RESULT. In 2025 the model gets the weather
                            FORECAST that was made 48 hours ahead, so it only
                            uses information a trader really had.
    OLS, actual weather     Upper bound. The model gets the weather that
                            actually happened (a perfect forecast).
    OLS, no weather         Lower bound. Same model without weather variables.

It saves:

    outputs/forecasts_test.csv   gets the columns ols_fc, ols_actual, ols_noweather
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
FORMULA_NO_WEATHER = "price ~ C(hour) + C(weekday) + C(month) + price_d1 + price_d7"

WEATHER = ["solar_wm2", "wind100_ms", "temp_c"]
MAIN_VARIABLES = ["price_d1", "price_d7"] + WEATHER
BEST_NAIVE = "Naive: same hour yesterday"


def main():
    df = pd.read_csv(DATA)
    train = df[df["split"] == "train"]
    test = df[df["split"] == "test"]

    # Fit on the training years only (with actual weather: forecasts do not
    # exist for 2023). HAC (Newey-West) standard errors, because hourly price
    # errors are correlated over time. This changes the t-values, not the
    # coefficients and not the forecasts.
    model = smf.ols(FORMULA, data=train).fit(cov_type="HAC", cov_kwds={"maxlags": 24})

    # 2025 with the weather FORECAST: same model, same coefficients. We only
    # swap the three weather columns for their forecast versions.
    test_with_forecast = test.copy()
    for name in WEATHER:
        test_with_forecast[name] = test[name + "_fc"]

    forecast_fc = model.predict(test_with_forecast)   # main result
    forecast_actual = model.predict(test)             # upper bound
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
        BEST_NAIVE: test["price_d1"],
        "Naive: same hour last week": test["price_d7"],
        "OLS, forecast weather": forecast_fc,
        "OLS, actual weather (upper bound)": forecast_actual,
        "OLS, no weather": forecast_no_weather,
    }
    results = pd.DataFrame({
        name: {
            "MAE": mae(test["price"], f),
            "RMSE": rmse(test["price"], f),
            "bias": float((f - test["price"]).mean()),   # forecast minus actual
        }
        for name, f in candidates.items()
    }).T
    best_naive = results.loc[BEST_NAIVE]
    results["MAE_vs_yesterday_%"] = (results["MAE"] / best_naive["MAE"] - 1) * 100
    results["RMSE_vs_yesterday_%"] = (results["RMSE"] / best_naive["RMSE"] - 1) * 100

    print("\nTEST SET 2025 (EUR/MWh; negative % = better than 'yesterday')")
    print(results.round(2).to_string())

    in_sample = model.predict(train)
    print(f"\nFor context, OLS on its own training data: "
          f"MAE {mae(train['price'], in_sample):.2f}   RMSE {rmse(train['price'], in_sample):.2f}")

    # Save.
    forecasts = pd.read_csv(OUT_DIR / "forecasts_test.csv")
    forecasts = forecasts.drop(columns=["ols"], errors="ignore")   # old column name
    forecasts["ols_fc"] = forecast_fc.to_numpy()
    forecasts["ols_actual"] = forecast_actual.to_numpy()
    forecasts["ols_noweather"] = forecast_no_weather.to_numpy()
    forecasts.to_csv(OUT_DIR / "forecasts_test.csv", index=False)
    results.round(2).to_csv(OUT_DIR / "results.csv", index_label="model")
    (OUT_DIR / "ols_summary.txt").write_text(model.summary().as_text(), encoding="utf-8")
    print("\nSaved: outputs/forecasts_test.csv, outputs/results.csv, outputs/ols_summary.txt")


if __name__ == "__main__":
    main()
