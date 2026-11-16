# PROGRESS

Project: forecast the Dutch day-ahead electricity price (hourly), one day ahead.
Question: does a simple OLS model beat a naive benchmark out-of-sample (test = 2025)?

To continue in a new session, say: "Read PROGRESS.md and continue with the next milestone."

## Status

| # | Milestone | Status |
|---|-----------|--------|
| 1 | Download + check data | DONE (2026-11-12) |
| 2 | Merge + features | DONE (2026-11-12) |
| 3 | Benchmarks (yesterday, last week) | DONE (2026-11-12) |
| 4 | OLS model | DONE (2026-11-12) |
| 5 | Evaluation + charts | DONE (2026-11-12) |
| 6 | README + 1-page PDF + CV bullet | DONE (2026-11-12) |
| – | Model B (LightGBM) | only if time is left |

## How to run

```
pip install -r requirements.txt
python data/download_data.py     # writes data/raw/*.csv (not in git)
python src/check_data.py         # prints checks, saves outputs/figures/01_data_check.png
python src/build_dataset.py      # writes data/processed/dataset.csv (not in git)
python src/benchmarks.py         # prints benchmark MAE/RMSE, writes outputs/forecasts_test.csv
python src/model_ols.py          # fits OLS, scores it with forecast / actual / no weather
python src/dm_test.py            # Diebold-Mariano test, adds DM columns to outputs/results.csv
python src/evaluate.py           # makes the two result charts in outputs/figures/
python battery/check_one_day.py  # checks the one-day battery LP against hand calculations
python battery/backtest.py       # trades the battery through 2025, writes outputs/battery/*.csv
python battery/sensitivity.py    # other battery durations and degradation costs
python battery/charts.py         # makes the two battery charts
python src/make_summary_pdf.py   # builds outputs/summary.pdf (two pages)
```

Or everything in one go: `python main.py` (add `--download` to fetch the data again).

## BATTERY PHASE (started 2026-11-16) – "How much money is a better price forecast worth?"

To continue in a new session, say: "Read PROGRESS.md and continue with the next battery milestone."

Goal: simulate a grid battery trading the Dutch day-ahead market in 2025. Each day: plan 24 hours
with a linear program on a price FORECAST, then settle against the ACTUAL prices.
Everything lives in the new folder `battery/`. Input: `outputs/forecasts_test.csv`.

Scope (strict, from Jip):
- Battery: 1 MW, 2 MWh, 90% round-trip efficiency, max 1 full cycle per day, starts and ends each
  day at 50%. Degradation cost 10 EUR/MWh discharged (a parameter).
- 4 forecasts: perfect foresight (`price`), OLS forecast weather (`ols_fc`, main),
  naive yesterday (`naive_d1`), OLS no weather (`ols_noweather`).
- Metrics: realised profit 2025 (EUR), capture rate = profit / perfect-foresight profit,
  value of forecasting = profit(OLS) - profit(naive) in EUR per MW per year.
- Sensitivity (only these): duration 1h / 2h / 4h; degradation 0 / 10 / 20 EUR/MWh.
- Charts: cumulative profit over 2025 per forecast; one example day (prices + charge/discharge).
- Limitations to list in README: no intraday/balancing market, no grid fees, price-taker, hourly not 15-min.
- Be honest: if the better forecast adds little money, say so and explain why.
- Stop after each milestone and show Jip. Give 3–5 interview bullets each time.

| # | Battery milestone | Status |
|---|-------------------|--------|
| B1 | LP for one day + check by hand | DONE (2026-11-16) |
| B2 | Full 2025 run for the 4 forecasts | DONE (2026-11-16) |
| B3 | Sensitivity (duration, degradation) | DONE (2026-11-16) |
| B4 | Charts | DONE (2026-11-16) |
| B5 | README section "From forecast to profit", PDF, CV bullet | DONE (2026-11-16) |
| B6 | Commit + push | DONE (2026-11-16) |

The battery phase is complete.

### B1 – one-day LP (DONE)

Files made: `battery/battery_lp.py` (the model), `battery/check_one_day.py` (the checks).
`scipy>=1.11` added to `requirements.txt`. Not yet in `main.py` (add the battery step in B2).

Functions in `battery_lp.py`:
- `Battery(...)` – dataclass with all settings (power, duration, efficiency, cycles, start level, degradation).
- `optimise_day(prices, battery)` – solves the LP (scipy `linprog`, HiGHS). Returns charge, discharge, soc.
- `settle(plan, actual_prices, battery)` – real profit of a plan at the actual prices.
- `check_plan(plan, battery)` – True/False per battery rule.

The LP, per hour t (variables: charge, discharge, soc):
- Maximise: sum of price x discharge - price x charge - degradation x discharge.
- 1. Energy balance: soc[t] = soc[t-1] + 0.949 x charge[t] - discharge[t] / 0.949.
- 2. One inverter: charge[t] + discharge[t] <= 1 MW.
- 3. Cycle limit: energy taken out of the battery per day <= 1 x capacity (2 MWh).
- 4. Power: 0 <= charge, discharge <= 1 MW.
- 5. Capacity: 0 <= soc <= 2 MWh.
- 6. Start and end of day at 50% (1 MWh).

Modelling choices (say these in the README):
- The 90% round trip is split evenly: sqrt(0.9) = 0.949 in each direction.
- "1 cycle" is measured inside the battery: 2 MWh taken out = 1.897 MWh sold to the grid.
- Degradation cost is per MWh SOLD to the grid.
- Days are Dutch local days (the `date` column), so the LP handles 23- and 25-hour days.
- It is a pure LP (no yes/no variables). Constraint 2 makes charging and discharging in the same
  hour unattractive, but cannot forbid it. It could happen at very negative prices with a full
  battery (burning energy to get paid). `check_plan` counts this. CHECK IN B2 how often it happens.

Checks (`python battery/check_one_day.py`, all passed):

| Check | LP | By hand |
|-------|----|---------|
| A. Toy day, battery without losses | 160.00 EUR | -10 + 120 + 100 - 50 = 160 |
| B. Same toy day, real battery | 125.35 EUR | 125.35 (formula in the script) |
| C. Flat prices | 0.00 EUR (does nothing) | 0 |
| D. Real day 14 May 2025, perfect foresight | 349.24 EUR | all 6 battery rules hold |

Toy day = 50 EUR/MWh all day, hour 3 = 10, hour 19 = 120, hour 20 = 100.

### B2 – full 2025 run (DONE 2026-11-16)

File made: `battery/backtest.py`. Added to `main.py` as step 7 (with `check_one_day.py`).
Outputs in `outputs/battery/`: `results.csv`, `daily_profit.csv`, `schedules.csv` (hourly plans).
Reusable functions for B3/B4: `load_data()`, `run_backtest(data, battery)`, `summarise(...)`.

Battery 1 MW / 2 MWh, 90% round trip, 1 cycle per day, degradation 10 EUR/MWh. 365 days of 2025.

| Forecast | Profit 2025 (EUR) | Capture rate | Hour ranking score | Days with a loss |
|----------|-------------------|--------------|--------------------|------------------|
| Perfect foresight (upper bound) | 62,869 | 100.0% | 1.00 | 0 |
| **OLS, forecast weather (main)** | **54,997** | **87.5%** | 0.87 | 6 |
| Naive: same hour yesterday | 50,485 | 80.3% | 0.78 | 22 |
| OLS, no weather | 53,357 | 84.9% | 0.83 | 14 |

- **Value of forecasting = 54,997 - 50,485 = 4,513 EUR per MW per year** (+8.9% vs naive, 12.4 EUR per day).
- It is real, not noise: daily gain 12.4 EUR, Newey-West t = 6.8 (7 lags). OLS wins on 59% of days,
  loses on 32%, ties on 9%. (Now in the repo: `backtest.py` writes `value_of_forecasting.csv`
  and `profit_by_month.csv`.)
- **Honest point 1: 24% better MAE became only 9% more profit.** The battery needs the ORDER of the
  hours (when is it cheap, when expensive), not the price level. The naive forecast gets the order
  mostly right already (ranking score 0.78 vs 0.87). A big part of the naive error is the daily price
  LEVEL (18.4 EUR/MWh vs 11.0 for OLS), and a level error costs the battery nothing.
- **Honest point 2: weather adds little money.** OLS without weather already gets 84.9%.
  Weather adds 1,640 EUR per year (t = 2.7). For MAE, weather was most of the gain; for profit it is
  about one third. From March to September "no weather" even earns slightly more than the main model.
- **Where the gain comes from:** winter. Jan + Feb + Oct + Nov + Dec = 2,831 of the 4,513 EUR.
  In April the gain is 5 EUR. In summer the solar pattern repeats every day, so "yesterday" is a
  good plan. Mondays gain most (+36 EUR per day): for naive, "yesterday" is a Sunday.
- The naive forecast is not bad at all: 80% of the perfect profit with zero modelling.
- Even perfect foresight is only 62,869 EUR per MW per year in the day-ahead market alone.
- Average buy / sell price (EUR/MWh): perfect 36.6 / 142.4, OLS 41.3 / 135.3, naive 42.1 / 130.5.
- Checks: all 1,460 daily plans obey all battery rules. **0 hours with charge and discharge together**,
  so the pure LP is fine (no need for yes/no variables). Profit recomputed from `schedules.csv` matches.

### B3 – sensitivity (DONE 2026-11-16)

File made: `battery/sensitivity.py` (in `main.py` as step 7). Output: `outputs/battery/sensitivity.csv`.
One thing changed at a time. 5 different batteries, 4 forecasts each. The base case gives exactly
the B2 numbers again. Profit in EUR per MW per year, 2025.

A. Battery duration (degradation 10 EUR/MWh):

| Duration | Perfect | OLS (main) | Naive | OLS no weather | OLS capture | Naive capture | Value of forecasting |
|----------|---------|------------|-------|----------------|-------------|---------------|----------------------|
| 1 h | 32,841 | 28,375 | 25,948 | 27,384 | 86.4% | 79.0% | 2,428 (+9.4%) |
| **2 h (base)** | 62,869 | 54,997 | 50,485 | 53,357 | 87.5% | 80.3% | 4,513 (+8.9%) |
| 4 h | 109,445 | 98,313 | 90,678 | 96,242 | 89.8% | 82.9% | 7,635 (+8.4%) |

B. Degradation cost (duration 2 h):

| Degradation (EUR/MWh) | Perfect | OLS (main) | Naive | OLS no weather | OLS capture | Naive capture | Value of forecasting |
|-----------------------|---------|------------|-------|----------------|-------------|---------------|----------------------|
| 0 | 69,773 | 61,923 | 57,428 | 60,282 | 88.7% | 82.3% | 4,495 (+7.8%) |
| **10 (base)** | 62,869 | 54,997 | 50,485 | 53,357 | 87.5% | 80.3% | 4,513 (+8.9%) |
| 20 | 56,127 | 47,777 | 43,807 | 46,399 | 85.1% | 78.0% | 3,970 (+9.1%) |

- **The conclusion is robust.** In all 5 cases OLS beats naive by 8–9% (7.8% to 9.4%), and the order
  of the four forecasts never changes.
- In EUR the value of forecasting grows with battery size (2,428 / 4,513 / 7,635), simply because a
  bigger battery trades more energy. As a percentage it stays the same.
- **Longer battery = forecast errors matter less.** Capture rate 86.4% -> 87.5% -> 89.8%. A 4 h battery
  spreads its trades over many hours, so missing THE cheapest or dearest hour hurts less.
- **Diminishing returns to size.** Perfect profit per MWh of capacity: 32.8k (1 h), 31.4k (2 h),
  27.4k (4 h). The extra hours it trades have a smaller price spread.
- **Higher degradation = forecast errors matter more.** Capture rate 88.7% -> 87.5% -> 85.1%.
  The battery must now also decide IF a trade is worth it. OLS loss days: 2 / 6 / 24.
  At 20 EUR/MWh perfect foresight skips trades (347 cycles), OLS still trades 362: it over-trades.
- Each 10 EUR/MWh of degradation costs about 7,000 EUR per year (about 1.9 MWh sold x 365 days x 10).

### B4 – charts (DONE 2026-11-16)

File made: `battery/charts.py`. Outputs: `outputs/figures/04_battery_cumulative_profit.png`,
`outputs/figures/05_battery_example_day.png`.

- Chart 1: cumulative profit over 2025, one line per forecast, totals written at the line ends.
- Chart 2: example day. Top = actual price and OLS forecast. Bottom = charge / discharge bars of
  the OLS plan.
- **Example day: Monday 24 February 2025.** Chosen by a rule: the 24-hour day with the median
  OLS-plan profit. Profit that day: OLS plan 136 EUR, perfect foresight 141 EUR, naive plan 38 EUR.
- The day shows the main finding: at night the forecast is 50–70 EUR/MWh too high, but the plan is
  almost perfect, because the cheap and expensive hours are in the right place.
- Be honest in an interview: this ONE day flatters OLS (97% capture, naive does badly because
  "yesterday" was a Sunday). Over the year it is 87.5% vs 80.3%.
- Colours: perfect/actual black, OLS blue `#2a78d6`, naive orange `#eb6834`, OLS no weather aqua
  `#1baf7a` (checked for colour-blind safety).

### B5 – README, PDF, CV bullet (DONE 2026-11-16)

- `README.md`: new section "From forecast to profit" (set-up, LP, results table, why 24% -> 9%,
  sensitivity table, 2 charts, limitations). Intro, "How to run" and folder structure updated.
- `src/make_summary_pdf.py` rewritten for two pages (small `Page` class). Page 1 is the old page.
  Page 2 is the battery page; it reads its numbers from `outputs/battery/*.csv`.
- `main.py` order: steps 1–5 forecast, step 6 battery (check, backtest, sensitivity, charts),
  step 7 PDF. `python main.py` ran end to end without errors (2026-11-16).

**CV bullet for the battery extension (add it under the forecasting bullet):**

> Quantified the value of the forecast with a battery-dispatch linear program (Python, HiGHS):
> a simulated 1 MW / 2 MWh battery on the Dutch day-ahead market earned 9% more with the OLS
> forecast than with a naive forecast (about EUR 4,500 per MW per year, 2025 out-of-sample),
> capturing 87% of perfect-foresight profit.

Shorter version:

> Simulated battery trading on the Dutch day-ahead market with a linear program; the OLS forecast
> added 9% profit vs. a naive forecast (EUR 4,500 per MW per year, 2025 out-of-sample).

Exact numbers behind it: 54,997 vs 50,485 EUR (+4,513, +8.9%), perfect foresight 62,869,
capture 87.5% vs 80.3%, Newey-West t = 6.8.
Do NOT call it a business case or "battery revenue": it is the day-ahead market only, with no
intraday or balancing income and no grid fees. Be ready to say that 24% better MAE gave only 9%
more profit, and why (the battery needs the order of the hours, not the price level).

### B6 – commit + push

See the status table at the top of this section.

## UPGRADE PHASE (started 2026-11-12)

Goal: make the result truly out-of-sample and statistically tested. Two upgrades, nothing else:
(1) real weather forecasts instead of actual weather, (2) Diebold-Mariano test.
Keep all old results as comparison rows.

| # | Upgrade milestone | Status |
|---|-------------------|--------|
| U1 | Check which Open-Meteo forecast data exists for 2023–2025 | DONE |
| U2 | Jip decides the split + forecast lead time | DONE: Jip said "Yes, go ahead" with the recommended plan |
| U3 | Download forecast weather, add to dataset | DONE |
| U4 | Re-run models with forecast weather | DONE (Jip chose RAW forecasts, no level correction) |
| U5 | Diebold-Mariano test (daily mean abs-error loss, HAC) | DONE |
| U6 | Update README, PDF, PROGRESS, new CV bullet | DONE |
| U7 | Commit + push to GitHub (remote origin = github.com/JipdeBoerEUR/Dutch-day-ahead-electricity-price-forecast) | DONE (2026-11-12) |

### U1 – what the Open-Meteo forecast archives cover (checked by API calls, De Bilt + Groningen)

**Previous Runs API** (`previous-runs-api.open-meteo.com`, variables `*_previous_day1`, `*_previous_day2`):
- 2023: NO data. Model `icon_seamless` (same for default `best_match`):
  solar + temperature start 19–20 Jan 2024, wind 100 m starts 16–17 Feb 2024.
- All three variables, day1 and day2, complete from **17 Feb 2024 12:00 UTC**. 0 gaps after that. 2025 is 100% complete.
- Other models start later (ECMWF, KNMI: March 2024). GFS has temperature for 2023 but not solar/wind.
- Meaning of the names (Open-Meteo docs): `_previous_day1` = value predicted 24 hours before the
  valid time, `_previous_day2` = 48 hours before.

**Historical Forecast API** (`historical-forecast-api.open-meteo.com`):
- Covers all of 2023–2025 with no gaps (best_match, ICON, GFS, KNMI).
- BUT it glues together the newest model runs, so each value is a forecast only a few hours old.
  That is almost the same as actual weather. It is NOT a day-ahead forecast, so it does not fix the problem.

**Two problems found:**
1. `_previous_day1` leaks for afternoon hours. The auction closes at 12:00 on D-1. A forecast made
   24 hours before delivery hour 15:00 was made at 15:00 on D-1, after the auction closed.
   Only `_previous_day2` (made on D-2) is safely before the deadline for all 24 hours.
2. Forecast data starts 17 Feb 2024, so a model trained on forecasts has only 10.5 months of training
   data, with no January and almost no February. The January month dummy cannot be estimated.

**Proposed plan (recommended, waiting for Jip's OK):**
- Keep train = 2023–2024 and test = 2025 unchanged. Keep the same model and coefficients
  (fitted on actual weather). In 2025, feed the model the real forecast instead of actual weather.
- Use `_previous_day2` for all hours, model `icon_seamless`, same 5 locations.
- Alternative (Option A): train on forecast weather only, 18 Feb – 31 Dec 2024, test 2025,
  without month dummies. Consistent inputs, but short training period and a changed model.

Note: the Previous Runs API is slow (requests for 2 years timed out at 180 s). The download script
asks for 3 months at a time with retries.

### U3 – forecast weather downloaded and added (decision: recommended plan)

Files changed: `data/download_data.py` (new function `download_weather_forecast`, skips files that
already exist, `--force` to download again), `src/build_dataset.py`, `main.py`.
New raw file: `data/raw/weather_forecast_nl_hourly.csv` (2025 only, 8,760 rows, 0 gaps, 0 duplicates).
New dataset columns: `solar_wm2_fc`, `wind100_ms_fc`, `temp_c_fc` (empty before 2025, complete in 2025).
New output: `outputs/weather_forecast_quality.csv`.

Settings: model `icon_seamless`, lead `previous_day2` (predicted 48 hours before the hour), same 5 locations.
All 5 locations downloaded without gaps, so the coverage is confirmed for every location.

Forecast vs actual weather in 2025:

| Variable | Mean actual | Mean forecast | Bias | MAE | Correlation |
|----------|-------------|---------------|------|-----|-------------|
| Solar (W/m²) | 142.85 | 134.19 | -8.66 | 18.81 | 0.98 |
| Wind 100 m (m/s) | 6.73 | 7.73 | +1.00 | 1.25 | 0.93 |
| Temperature (°C) | 11.42 | 11.50 | +0.08 | 0.63 | 0.99 |

**Finding: the wind forecast is on average 1.0 m/s higher than the "actual" wind.** The two come from
different weather models (forecast = DWD ICON, actual = ERA5 reanalysis), so part of this is a level
difference between the products, not only forecast error. The OLS wind coefficient is -6.07 EUR/MWh
per m/s, so feeding raw forecasts will push the price forecast about 6 EUR/MWh down on average.
This must NOT be corrected with 2025 data (that would be look-ahead). A fair correction would use
forecasts and actuals from 17 Feb – 31 Dec 2024 only. Decide BEFORE looking at the model results.

### U4 – models re-run with forecast weather (raw forecasts, decided before looking at results)

Files changed: `src/model_ols.py`, `src/evaluate.py`.
`outputs/forecasts_test.csv` now has columns `ols_fc` (main), `ols_actual`, `ols_noweather` (old column `ols` = `ols_actual`).
`outputs/results.csv` has a new `bias` column (forecast minus actual).

Test set 2025. Model fitted once on 2023–2024 with actual weather; only the 2025 inputs differ per row.

| Model | MAE | RMSE | Bias | MAE vs yesterday | RMSE vs yesterday |
|-------|-----|------|------|------------------|-------------------|
| Naive: same hour yesterday | 23.94 | 37.23 | -0.04 | – | – |
| Naive: same hour last week | 30.09 | 45.69 | +0.31 | +25.7% | +22.7% |
| **OLS, forecast weather (MAIN)** | **18.29** | **26.33** | **-1.97** | **-23.6%** | **-29.3%** |
| OLS, actual weather (upper bound, old result) | 17.79 | 25.87 | +3.36 | -25.7% | -30.5% |
| OLS, no weather | 21.65 | 31.30 | -0.04 | -9.6% | -15.9% |

- **Honest headline: -23.6% MAE with real 48-hour weather forecasts** (was -25.7% with perfect weather).
  Real forecasts cost only 0.50 EUR/MWh of MAE. Most of the weather gain survives.
- Bias moved from +3.36 to -1.97, as expected from the +1.0 m/s wind forecast bias.
- Charts now show the main model (`ols_fc`). Sample week by the same median rule is now 3–9 Feb 2025
  (OLS MAE 17.61, naive 22.37; best week 11.19, worst week 31.76).
- By hour: OLS still wins in 24 of 24 hours, but at night (hours 22–4) the gain is now only 1–7%.
  Morning ramp (hours 6–9) still about -31% to -39%.

KNOWN BROKEN until U6: `src/make_summary_pdf.py` still looks for the old row names
("OLS regression", "OLS without weather (check)"). Fix it in U6 together with README.

Next (U5): add `src/dm_test.py`. Diebold-Mariano test vs "same hour yesterday" for `ols_fc`,
`ols_actual`, `ols_noweather`. Loss = absolute error. Average the loss difference per delivery day
(365 values), then test mean = 0 with Newey-West (HAC) standard errors. Report DM statistic + p-value,
and add both to `outputs/results.csv`.

### U5 – Diebold-Mariano test

File made: `src/dm_test.py` (added to `main.py` after the OLS step).
It adds `DM_stat` and `DM_p_value` to `outputs/results.csv`.

Method: loss = absolute error. Loss difference = naive loss minus model loss, averaged per delivery
day (365 days). Test mean = 0 with Newey-West (HAC) standard errors, 7 lags. Two-sided p-value.
Positive DM = model better than "same hour yesterday".

| Model | Mean daily gain (EUR/MWh) | Days better | DM statistic | p-value |
|-------|---------------------------|-------------|--------------|---------|
| Naive: same hour last week | -6.15 | 40.5% | -4.45 | 8.6e-06 |
| **OLS, forecast weather (MAIN)** | **5.65** | **66.0%** | **6.81** | **9.8e-12** |
| OLS, actual weather (upper bound) | 6.15 | 66.6% | 7.76 | 8.7e-15 |
| OLS, no weather | 2.29 | 57.8% | 4.21 | 2.6e-05 |

- **All three OLS versions are significantly better than the naive forecast (p < 0.001).**
- "Last week" is significantly WORSE than "yesterday".
- Robust to the lag choice: for the main model DM = 8.55 / 6.81 / 6.39 / 6.34 with 0 / 7 / 14 / 28 lags.
- Honest nuance: the OLS model is better on 66% of days, not on all days. It loses on 1 day in 3.

Next (U6): fix `src/make_summary_pdf.py` (new row names + DM columns), rewrite README results and
limitations, new CV bullet. Headline numbers: MAE 18.29 vs 23.94 (-23.6%), RMSE 26.33 vs 37.23 (-29.3%),
DM 6.81, p < 0.001. Then U7: commit + push.

### U6 – documents updated

Files changed: `README.md` (results, method, limitations, next steps), `src/make_summary_pdf.py`
(new 5-row table with DM statistic and p-value) -> `outputs/summary.pdf`.
`python main.py` ran end to end without errors after the changes. All numbers come from that run.

**NEW CV bullet (use this one; it replaces the bullet in "Milestone 6" below):**

> Built a day-ahead power price forecasting model for the Netherlands in Python on public
> Fraunhofer ISE and Open-Meteo data; using only weather forecasts available before gate closure,
> an OLS regression cut MAE by 24% vs. a naive benchmark out-of-sample (2025), statistically
> significant in a Diebold-Mariano test (p < 0.001).

Shorter version:

> Built a Dutch day-ahead power price model on public Fraunhofer ISE/Open-Meteo data; cut MAE by
> 24% vs. a naive benchmark out-of-sample (2025, Diebold-Mariano p < 0.001).

Exact numbers behind it: MAE 18.29 vs 23.94 EUR/MWh (-23.6%), RMSE 26.33 vs 37.23 (-29.3%), DM 6.81.

Next (U7): commit + push to the remote origin (Jip has already added it).

## Milestone 1 – result

Files made:
- `data/download_data.py` – downloads prices + weather
- `src/check_data.py` – data-quality report + one chart
- `requirements.txt`, `.gitignore`

Data:
- Prices: energy-charts.info API (Fraunhofer ISE), bidding zone NL, EUR/MWh. It worked, so ENTSO-E was not needed.
- Weather: Open-Meteo archive API, 5 locations averaged (De Bilt, Groningen, Eindhoven, Vlissingen, Den Helder).
  Columns: `solar_wm2`, `wind100_ms`, `temp_c`.
- Period: 2023-01-01 to 2025-12-31, Dutch local time. Timestamps stored in UTC (start of hour).

Checks (all passed):
- 26,304 hourly rows in both files = exactly what is expected. 0 missing, 0 duplicates, 0 empty values.
- Extreme prices are real events, not errors: -500 on 2 July 2023 (sunny Sunday), 873 on 12 Dec 2024 (no wind, no sun).

| Year | Mean | Median | Min | Max | Negative hours |
|------|------|--------|-----|-----|----------------|
| 2023 | 95.8 | 99.2 | -500.0 | 463.8 | 3.6% |
| 2024 | 77.3 | 80.0 | -200.0 | 873.0 | 5.2% |
| 2025 | 86.8 | 90.4 | -350.0 | 523.5 | 6.7% |

Correlation with price (same hour): solar -0.42, wind -0.32, temperature -0.29.

## Decisions and things to remember

1. **15-minute prices from 1 Oct 2025.** The market switched from hourly to 15-minute prices.
   I take the average of the 4 quarters to get one hourly price. Mention in README limitations.
2. **Time zones.** Data is stored in UTC. Hour-of-day, weekday and month must use Dutch local time
   (`Europe/Amsterdam`), because the market and people's behaviour follow local time.
   Clock-change days have 23 or 25 hours – handle this when making the D-1 and D-7 lags.
3. **No look-ahead.** The auction for day D closes at 12:00 on day D-1. At that moment all prices of
   day D-1 are already known (published on D-2). So "same hour yesterday" is allowed for every hour.
4. **Weather is a proxy.** We use actual weather for day D as if it were the forecast. A real forecast
   has errors, so our model result is a bit too optimistic. Must be in README limitations.
5. First 7 days of 2023 will be dropped in milestone 2 (no D-7 lag available).

## Milestone 2 – result

File made: `src/build_dataset.py` -> `data/processed/dataset.csv`

Columns: `time_utc, date, year, month, weekday, hour, price, price_d1, price_d7, solar_wm2, wind100_ms, temp_c, split`
(`date`, `hour`, `weekday`, `month` are Dutch local time; weekday 0 = Monday.)

- 26,136 rows, 0 empty values. First 7 days (168 hours) dropped because they have no D-7 price.
- Train: 2023-01-08 to 2024-12-31 = 17,376 hours. Test: 2025-01-01 to 2025-12-31 = 8,760 hours.
- Lags are looked up by clock hour, not by shifting 24 rows. Checked on the clock-change days
  (30 March 2025 and 26 October 2025): correct. On normal days the lag equals a plain 24-row shift.
  - 25-hour day: the repeated 02:00 hour uses the average of the two prices as lag value.
  - 23-hour day: the missing 02:00 hour is filled in between 01:00 and 03:00.
- Correlation with price (train only): price_d1 0.67, price_d7 0.55, solar -0.38, wind -0.34, temp -0.26.

## Milestone 3 – result

Files made: `src/metrics.py` (MAE, RMSE), `src/benchmarks.py`
Outputs: `outputs/forecasts_test.csv` (actual + `naive_d1` + `naive_d7`), `outputs/results_benchmarks.csv`

Test set 2025 (8,760 hours, average price 86.8 EUR/MWh):

| Benchmark | MAE | RMSE |
|-----------|-----|------|
| Same hour yesterday | 23.94 | 37.23 |
| Same hour last week | 30.09 | 45.69 |

- **The bar to beat is "yesterday": MAE 23.94, RMSE 37.23.** It is the stronger benchmark.
- For context on 2023–2024: yesterday MAE 26.04 / RMSE 40.82, last week MAE 30.63 / RMSE 47.53.
  So 2025 was slightly EASIER for the naive forecast than the training years, even with more
  negative hours. (Earlier guess that 2025 would be harder was wrong.)

## Milestone 4 – result

File made: `src/model_ols.py`
Outputs: `outputs/results.csv`, `outputs/ols_summary.txt`, column `ols` in `outputs/forecasts_test.csv`

Model: `price ~ C(hour) + C(weekday) + C(month) + price_d1 + price_d7 + solar_wm2 + wind100_ms + temp_c`
Fitted once on 2023–2024 (17,376 hours, 46 coefficients, R² 0.692). Not refitted, not tuned on 2025.

Test set 2025:

| Model | MAE | RMSE | MAE vs yesterday | RMSE vs yesterday |
|-------|-----|------|------------------|-------------------|
| Naive: same hour yesterday | 23.94 | 37.23 | – | – |
| Naive: same hour last week | 30.09 | 45.69 | +25.7% | +22.7% |
| **OLS regression** | **17.79** | **25.87** | **-25.7%** | **-30.5%** |
| OLS without weather (check) | 21.65 | 31.30 | -9.6% | -15.9% |

- **OLS beats the best naive benchmark: MAE -25.7%, RMSE -30.5%.**
- **Honesty check (added, small):** weather is actual weather, not a forecast. Without weather the
  gain is only -9.6% MAE. A real forecast would land between -9.6% and -25.7%. Say this in the README.
- Coefficients (HAC/Newey-West standard errors, 24 lags):
  price_d1 0.356 (t 8.6), price_d7 0.195 (t 7.5), solar -0.086 per W/m² (t -13.1),
  wind -6.07 per m/s (t -24.5), temp -0.33 per °C (t -1.6, NOT significant).
- Signs are as expected: more sun or wind = lower price (merit order).
- OLS forecasts are on average 3.36 EUR/MWh too high in 2025 (small bias).
- No overfitting: train MAE 18.60 vs test MAE 17.79.

## Milestone 5 – result

File made: `src/evaluate.py`
Outputs: `outputs/figures/02_sample_week.png`, `outputs/figures/03_mae_by_hour.png`, `outputs/mae_by_hour.csv`

- **Sample week: 10–16 Feb 2025.** Chosen by a fixed rule, not by eye: of the 49 full Mon–Sun weeks
  in 2025 (the 2 clock-change weeks are left out), it is the one with the MEDIAN OLS error.
  MAE that week: OLS 17.02, naive 22.20. Best week OLS 11.29, worst week 28.06.
- **OLS beats the naive forecast in all 24 hours of the day.**
  - Biggest gain: morning ramp, hours 6–9 (about -40%). Naive MAE peaks at 33.7 at hour 8.
  - Smallest gain: late evening and night, hours 22–2 (about -14% to -19%).
  - OLS is best at hour 5 (MAE 13.0) and worst at hour 19 (MAE 22.7).
- Visible weakness in the week chart: OLS misses the size of evening price spikes
  (Fri 14 Feb: actual about 275, OLS about 200). A linear model smooths extremes.
- Chart colours: actual = black, OLS = blue `#2a78d6`, naive = orange `#eb6834` (colour-blind safe).

## Milestone 6 – result

Files made: `README.md`, `main.py` (runs all steps), `src/make_summary_pdf.py` -> `outputs/summary.pdf`

- `python main.py` was run end to end without errors. All numbers in README and PDF come from that run.
- The PDF reads its numbers from `outputs/results.csv`, so it cannot drift from the real results.
- To add a surname to the PDF: change `AUTHOR` at the top of `src/make_summary_pdf.py` and re-run it.

**OLD CV bullet (superseded by the one in section U6, kept for the record):**

> Built a day-ahead power price forecasting model for the Netherlands in Python on public
> Fraunhofer ISE and Open-Meteo data (26,000 hourly observations); an OLS regression reduced MAE
> by 26% vs. a naive benchmark out-of-sample (2025), and by 10% without weather inputs.

Shorter version:

> Built a Dutch day-ahead power price model on public Fraunhofer ISE/Open-Meteo data; reduced MAE
> by 26% vs. a naive benchmark out-of-sample (2025).

Note: the price data is from energy-charts (Fraunhofer ISE), NOT ENTSO-E. Do not write ENTSO-E on the CV.
If you use the shorter version, be ready to say in the interview that actual weather was used as the forecast.

## The project is complete. Optional next steps (only if Jip asks)

- Model B: LightGBM as a comparison (in the original scope as "only if time is left").
- Git: repository made and first commit done on branch `main` (2026-11-12). Raw data is not in git.
- Still to do by Jip: make an empty repository on github.com, then
  `git remote add origin <url>` and `git push -u origin main`.
