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
python src/model_ols.py          # fits OLS, adds column "ols", writes outputs/results.csv
python src/evaluate.py           # makes the two result charts in outputs/figures/
python src/make_summary_pdf.py   # builds outputs/summary.pdf
```

Or everything in one go: `python main.py` (add `--download` to fetch the data again).

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

**CV bullet (recommended, honest version):**

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
- Put the folder on GitHub: `git init`, first commit, push. Not done yet.
