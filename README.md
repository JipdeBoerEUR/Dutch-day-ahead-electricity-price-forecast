# Forecasting the Dutch day-ahead electricity price

A small, honest forecasting project: does a simple econometric model beat a naive benchmark
when it forecasts tomorrow's hourly Dutch power price on a year it has never seen?

**Short answer: yes.** On the 2025 test set, an OLS regression lowers the mean absolute error
by 23.6% against the best naive benchmark. It only uses weather forecasts that were available before
the auction closed. A Diebold-Mariano test shows the gain is statistically significant
(DM = 6.81, p < 0.001).

A one-page summary is in [outputs/summary.pdf](outputs/summary.pdf).

## Question

The day-ahead auction sets one price for each hour of the next day. Bids close at 12:00 the day
before. Can a simple model, using only information available before that deadline, forecast those
prices better than "the same as yesterday"?

## Data

All data is public and free. Nothing is stored in this repository: the download script fetches it.

| Data | Source | Details |
|------|--------|---------|
| Day-ahead prices | [energy-charts.info](https://www.energy-charts.info) API (Fraunhofer ISE) | Bidding zone NL, EUR/MWh |
| Actual weather | [Open-Meteo](https://open-meteo.com) historical weather API | Used to fit the model (2023–2024) |
| Weather forecasts | Open-Meteo previous-runs API, DWD ICON model | Used to forecast 2025, made 48 hours ahead |

- Weather variables: solar radiation, wind speed at 100 m, temperature.
- Weather is the average of 5 locations: De Bilt, Groningen, Eindhoven, Vlissingen, Den Helder.
- Period: 1 January 2023 to 31 December 2025 (the 2022 energy crisis is left out).
- 26,304 hourly observations. No missing hours, no duplicates.
- Train: 2023–2024 (17,376 hours). Test: 2025 (8,760 hours).

## Method

**Benchmarks** (no fitting needed):

1. Same hour yesterday.
2. Same hour last week.

**Model: OLS regression**, fitted once on 2023–2024 and then used unchanged on 2025:

```
price = hour dummies + weekday dummies + month dummies
        + price yesterday + price last week
        + solar radiation + wind speed + temperature + error
```

**No look-ahead.** The auction for day D closes at 12:00 on day D-1.

- Lagged prices: the prices of day D-1 were published the day before, so they are known in time.
- Weather: in 2025 the model gets the forecast that was made 48 hours before each hour. That
  forecast was always made on day D-2, before the auction closed. A 24-hour-old forecast would not
  be safe: for afternoon hours it was made after 12:00 on D-1.
- The 2025 data was never used for fitting or tuning.

**Why the model is fitted on actual weather.** The forecast archive only starts in February 2024,
so there are no forecasts for 2023. The coefficients are therefore estimated on actual weather
(2023–2024), and the model is tested on real forecasts (2025).

**Significance test.** A Diebold-Mariano test compares each model with "same hour yesterday".
The loss is the absolute error. The loss difference is averaged per delivery day (365 days), because
the 24 hours of one day are forecast at the same moment. Standard errors are Newey-West (7 lags).

**Time handling.** Hour, weekday and month use Dutch local time. Lagged prices are matched by clock
hour, so the 23-hour and 25-hour clock-change days are handled correctly.

## Results

Test set: all 8,760 hours of 2025. Average price in 2025: 86.8 EUR/MWh.

| Model | MAE | RMSE | MAE vs naive | RMSE vs naive | DM stat | p-value |
|-------|-----|------|--------------|---------------|---------|---------|
| Naive: same hour yesterday | 23.94 | 37.23 | – | – | – | – |
| Naive: same hour last week | 30.09 | 45.69 | +25.7% | +22.7% | -4.45 | < 0.001 |
| **OLS, forecast weather** | **18.29** | **26.33** | **-23.6%** | **-29.3%** | **+6.81** | **< 0.001** |
| OLS, actual weather (upper bound) | 17.79 | 25.87 | -25.7% | -30.5% | +7.76 | < 0.001 |
| OLS, no weather | 21.65 | 31.30 | -9.6% | -15.9% | +4.21 | < 0.001 |

MAE and RMSE are in EUR/MWh. Negative % means a lower error than "same hour yesterday".
A positive DM statistic means the model is more accurate than "same hour yesterday".

How to read the three OLS rows:

- **Forecast weather** is the main result. It is what the model would really have achieved.
- **Actual weather** is the upper bound: a perfect weather forecast. Real forecasts cost only
  0.50 EUR/MWh of MAE.
- **No weather** is the lower bound. Most of the gain comes from the weather variables.

The OLS model is more accurate than "same hour yesterday" on 66% of the days in 2025.

Main coefficients (Newey-West standard errors):

| Variable | Coefficient | t-value | Meaning |
|----------|-------------|---------|---------|
| Price yesterday | 0.356 | 8.6 | Prices persist from day to day |
| Price last week | 0.195 | 7.5 | Weekly pattern |
| Solar radiation (W/m²) | -0.086 | -13.1 | More sun, lower price |
| Wind speed (m/s) | -6.07 | -24.5 | More wind, lower price |
| Temperature (°C) | -0.33 | -1.6 | Not significant |

The signs match the merit order: wind and solar have near-zero running cost and push more
expensive plants out of the market.

![Forecast vs actual in a typical week](outputs/figures/02_sample_week.png)

The sample week was chosen by a rule, not by eye: of all full weeks in 2025 it has the median OLS error.

![Error by hour of day](outputs/figures/03_mae_by_hour.png)

OLS beats the naive forecast in all 24 hours. The gain is largest in the morning ramp
(hours 6–9, 31–39%). At night (hours 22–4) it is small, only 1–7%.

## Limitations

- **Trained on actual weather, tested on forecasts.** The two come from different weather models
  (ERA5 reanalysis and DWD ICON). The wind forecast is on average 1.0 m/s higher than the actual
  wind data, which makes the price forecast about 2 EUR/MWh too low on average. I did not correct
  this, because a correction based on 2025 would be look-ahead.
- **48-hour-old forecasts for every hour.** This is stricter than reality. A trader has a fresher
  forecast for the morning hours.
- **One fixed fit.** The coefficients are estimated once. In practice you would re-estimate every day
  on a rolling window.
- **Missing drivers.** No gas price, CO2 price, load forecast, or cross-border flows.
- **Price spikes.** A linear model smooths extremes. It underestimates high evening peaks and does
  not capture negative prices well.
- **One test year.** The test is significant, but 2025 is a single year and one market regime.
- **15-minute prices.** From 1 October 2025 the market clears every 15 minutes. I average the four
  quarter-hours to get an hourly price.

## What I would do next

1. Train the model on forecasts too, once the forecast archive is long enough, or correct the level
   of the forecasts using data from before the test year.
2. Use the freshest forecast that is available at 12:00 on D-1 for each hour.
3. Re-estimate the model every day on a rolling window.
4. Add gas and CO2 prices and the ENTSO-E day-ahead load and wind/solar forecasts.
5. Compare with one non-linear model (for example LightGBM) to see if it handles spikes better.

## How to run

```
pip install -r requirements.txt
python main.py
```

`main.py` runs every step in order. Data files that already exist are not downloaded again;
add `--download` to fetch everything again. Each step can also be run on its own:

| Step | Script | What it does |
|------|--------|--------------|
| 1 | `data/download_data.py` | Downloads prices, weather and weather forecasts to `data/raw/` |
| 1 | `src/check_data.py` | Data-quality report |
| 2 | `src/build_dataset.py` | Merges the data and builds the features |
| 3 | `src/benchmarks.py` | Scores the two naive benchmarks |
| 4 | `src/model_ols.py` | Fits the OLS model and scores it |
| 4 | `src/dm_test.py` | Diebold-Mariano test against the naive benchmark |
| 5 | `src/evaluate.py` | Makes the two result charts |
| 6 | `src/make_summary_pdf.py` | Builds the one-page PDF |

## Folder structure

```
data/download_data.py     download script (raw data is not committed)
src/                      one script per step, plus metrics.py
outputs/results.csv       results table
outputs/figures/          charts
outputs/summary.pdf       one-page summary
main.py                   runs everything
requirements.txt
```

## Data credits

- Prices: energy-charts.info, Fraunhofer ISE. Licence CC BY 4.0.
- Weather and weather forecasts: Open-Meteo.com. Licence CC BY 4.0.

This is a student project. Python code was written with AI assistance.
