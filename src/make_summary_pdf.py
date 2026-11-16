"""Build the 2-page PDF summary.

Run from the project folder (after src/evaluate.py and battery/charts.py):

    python src/make_summary_pdf.py

Page 1: the price forecast. Numbers from outputs/results.csv.
Page 2: the battery ("from forecast to profit"). Numbers from outputs/battery/*.csv.
The charts come from outputs/figures/. Output: outputs/summary.pdf (two A4 pages).
"""

from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

AUTHOR = "Jip de Boer · BSc Econometrics & Operations Research, Erasmus University Rotterdam"

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"
BATTERY_DIR = OUT_DIR / "battery"

# A4 page in points (1 point = 1/72 inch). We place everything in points from the top-left.
PAGE_W, PAGE_H = 595, 842
LEFT, RIGHT = 48, 547
INK, MUTED, RULE = "#0b0b0b", "#52514e", "#c3c2b7"

BEST_NAIVE = "Naive: same hour yesterday"
MAIN_MODEL = "OLS, forecast weather"

# Row names in outputs/battery/results.csv
B_PERFECT = "Perfect foresight (upper bound)"
B_MAIN = "OLS, forecast weather (main)"
B_NAIVE = "Naive: same hour yesterday"

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]


def p_text(p):
    """Show a p-value the way a paper would."""
    if pd.isna(p):
        return "–"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


class Page:
    """One A4 page. Positions are in points from the top-left corner."""

    def __init__(self):
        self.fig = plt.figure(figsize=(PAGE_W / 72, PAGE_H / 72))

    def text(self, x, y, string, size=9.5, color=INK, weight="normal", align="left"):
        self.fig.text(x / PAGE_W, 1 - y / PAGE_H, string, fontsize=size, color=color,
                      fontweight=weight, ha=align, va="top", linespacing=1.4)

    def paragraph(self, y, string, size=9.5, color=INK, width=114):
        """Write wrapped text and return the y position just below it."""
        lines = textwrap.wrap(string, width=width)
        self.text(LEFT, y, "\n".join(lines), size=size, color=color)
        return y + len(lines) * size * 1.4

    def rule(self, y, color=RULE):
        self.fig.add_artist(Line2D([LEFT / PAGE_W, RIGHT / PAGE_W], [1 - y / PAGE_H] * 2,
                                   color=color, linewidth=0.8))

    def picture(self, path, top, width=415):
        image = mpimg.imread(path)
        height = width * image.shape[0] / image.shape[1]
        left = (PAGE_W - width) / 2
        ax = self.fig.add_axes([left / PAGE_W, 1 - (top + height) / PAGE_H,
                                width / PAGE_W, height / PAGE_H])
        ax.imshow(image, interpolation="none")
        ax.axis("off")
        return top + height

    def header(self, title, page_number):
        self.text(LEFT, 34, title, size=17, weight="bold")
        self.text(LEFT, 60, AUTHOR, size=9.5, color=MUTED)
        self.text(RIGHT, 60, f"Page {page_number} of 2", size=9.5, color=MUTED, align="right")
        self.rule(79)


def forecast_page():
    """Page 1: does the OLS model beat the naive forecast?"""
    results = pd.read_csv(OUT_DIR / "results.csv").set_index("model")
    naive = results.loc[BEST_NAIVE]
    main_row = results.loc[MAIN_MODEL]
    actual = results.loc["OLS, actual weather (upper bound)"]
    no_weather = results.loc["OLS, no weather"]

    page = Page()
    page.header("Forecasting the Dutch day-ahead electricity price", 1)

    # ---- Question and answer -------------------------------------------------
    page.text(LEFT, 87, "Question", weight="bold")
    y = page.paragraph(101, "Can a simple OLS regression forecast tomorrow's hourly Dutch day-ahead price "
                            "better than a naive rule, on a year of data it has never seen?")

    page.text(LEFT, y + 5, "Answer", weight="bold")
    y = page.paragraph(y + 19, (
        f"Yes. On the 2025 test set, OLS lowers the mean absolute error from {naive['MAE']:.2f} to "
        f"{main_row['MAE']:.2f} EUR/MWh ({main_row['MAE_vs_yesterday_%']:.1f}%) against the best naive "
        f"benchmark, using only weather forecasts that were available before the auction closed. "
        f"A Diebold-Mariano test shows the gain is statistically significant "
        f"(DM = {main_row['DM_stat']:.2f}, p {p_text(main_row['DM_p_value'])}). With perfect weather "
        f"the gain would be {abs(actual['MAE_vs_yesterday_%']):.1f}%; with no weather inputs "
        f"{abs(no_weather['MAE_vs_yesterday_%']):.1f}%."
    ))

    # ---- Results table -------------------------------------------------------
    y += 7
    page.text(LEFT, y, "Results on the 2025 test set (EUR/MWh, 8,760 hours)", weight="bold")
    y += 17
    columns = [(262, "MAE"), (312, "RMSE"), (384, "MAE vs naive"), (458, "RMSE vs naive"),
               (505, "DM stat"), (RIGHT, "p-value")]
    page.text(LEFT, y, "Model", size=8.5, color=MUTED)
    for x, label in columns:
        page.text(x, y, label, size=8.5, color=MUTED, align="right")
    y += 14
    page.rule(y)

    for model, row in results.iterrows():
        is_base = model == BEST_NAIVE
        weight = "bold" if model == MAIN_MODEL else "normal"
        y += 3
        page.text(LEFT, y, model, weight=weight)
        values = [
            f"{row['MAE']:.2f}",
            f"{row['RMSE']:.2f}",
            "–" if is_base else f"{row['MAE_vs_yesterday_%']:+.1f}%",
            "–" if is_base else f"{row['RMSE_vs_yesterday_%']:+.1f}%",
            "–" if is_base else f"{row['DM_stat']:+.2f}",
            p_text(row["DM_p_value"]),
        ]
        for (x, _), value in zip(columns, values):
            page.text(x, y, value, weight=weight, align="right")
        y += 14
    y += 3
    page.rule(y)
    y = page.paragraph(y + 4, (
        'Negative % = lower error than "same hour yesterday". DM = Diebold-Mariano test against '
        '"same hour yesterday" (absolute-error loss, averaged per day, Newey-West standard errors); '
        "positive = more accurate. Model fitted once on 2023–2024; 2025 was never used for fitting."
    ), size=8, color=MUTED, width=134)

    # ---- Charts ----------------------------------------------------------------
    y = page.picture(FIG_DIR / "02_sample_week.png", top=y + 2)
    y = page.picture(FIG_DIR / "03_mae_by_hour.png", top=y + 1)

    # ---- Method and limitations ----------------------------------------------
    y += 3
    page.rule(y)
    page.text(LEFT, y + 5, "Method and limitations", size=8.5, weight="bold")
    y = page.paragraph(y + 18, (
        "OLS with hour, weekday and month dummies, lagged prices, and solar radiation, 100 m wind "
        "speed and temperature (average of 5 Dutch locations). Fitted on 2023–2024 with actual "
        "weather; in 2025 it is fed forecasts made 48 hours ahead (DWD ICON). Limitations: trained "
        "on actual weather, tested on forecasts from another weather model (wind 1.0 m/s high); one "
        "fixed fit; no gas, CO2, load or cross-border inputs; a linear model underestimates price "
        "spikes; one test year; 15-minute prices (from Oct 2025) averaged to hourly."
    ), size=8, color=MUTED, width=134)
    y = page.paragraph(y + 3, "Data: energy-charts.info (Fraunhofer ISE), bidding zone NL, and Open-Meteo "
                              "(historical weather and previous-runs forecasts). Public, CC BY 4.0. "
                              "Code: Python, pandas, statsmodels.",
                       size=8, color=MUTED, width=134)
    return page.fig, y


def battery_page():
    """Page 2: how much money is the better forecast worth for a battery?"""
    results = pd.read_csv(BATTERY_DIR / "results.csv").set_index("forecast")
    value = pd.read_csv(BATTERY_DIR / "value_of_forecasting.csv").iloc[0]
    sensitivity = pd.read_csv(BATTERY_DIR / "sensitivity.csv")
    mae_gain = abs(pd.read_csv(OUT_DIR / "results.csv").set_index("model")
                   .loc[MAIN_MODEL, "MAE_vs_yesterday_%"])

    main_row, naive, perfect = results.loc[B_MAIN], results.loc[B_NAIVE], results.loc[B_PERFECT]

    # Over all sensitivity cases: by how much does OLS beat naive, in %?
    case_gain = []
    for _, case in sensitivity.groupby(["duration_h", "degradation_eur_mwh"]):
        profit = case.set_index("forecast")["profit_eur"]
        case_gain.append(profit[B_MAIN] / profit[B_NAIVE] - 1)

    page = Page()
    page.header("From forecast to profit: battery trading in 2025", 2)

    # ---- Question and answer -------------------------------------------------
    page.text(LEFT, 87, "Question", weight="bold")
    y = page.paragraph(101, "How much money is the better price forecast worth? A simulated 1 MW / 2 MWh "
                            "grid battery trades the Dutch day-ahead market through 2025 with each forecast.")

    page.text(LEFT, y + 5, "Answer", weight="bold")
    y = page.paragraph(y + 19, (
        f"About {value['value_eur_per_mw_year']:,.0f} EUR per MW per year. Planned on the OLS forecast "
        f"the battery earns {main_row['profit_eur']:,.0f} EUR, against {naive['profit_eur']:,.0f} EUR on "
        f"the naive forecast ({value['gain_vs_naive']:+.1%}, Newey-West t = {value['newey_west_t']:.1f}). "
        f"OLS captures {main_row['capture_rate']:.1%} of the perfect-foresight profit, naive "
        f"{naive['capture_rate']:.1%}. The gain is real, but much smaller than the {mae_gain:.0f}% gain "
        f"in MAE: a battery only needs the order of the hours within a day, and yesterday's prices "
        f"already give that order quite well."
    ))

    # ---- Results table -------------------------------------------------------
    y += 7
    page.text(LEFT, y, "Battery profit in 2025 (EUR per MW per year, 365 days)", weight="bold")
    y += 17
    columns = [(300, "Profit"), (366, "Capture rate"), (424, "vs naive"),
               (494, "Hour ranking"), (RIGHT, "Loss days")]
    page.text(LEFT, y, "Price forecast used for the plan", size=8.5, color=MUTED)
    for x, label in columns:
        page.text(x, y, label, size=8.5, color=MUTED, align="right")
    y += 14
    page.rule(y)

    for forecast, row in results.iterrows():
        weight = "bold" if forecast == B_MAIN else "normal"
        no_gain = forecast in (B_NAIVE, B_PERFECT)
        y += 3
        page.text(LEFT, y, forecast.replace(" (main)", ""), weight=weight)
        values = [
            f"{row['profit_eur']:,.0f}",
            f"{row['capture_rate']:.1%}",
            "–" if no_gain else f"{row['profit_eur'] - naive['profit_eur']:+,.0f}",
            f"{row['hour_ranking_score']:.2f}",
            f"{row['days_with_loss']:.0f}",
        ]
        for (x, _), cell in zip(columns, values):
            page.text(x, y, cell, weight=weight, align="right")
        y += 14
    y += 3
    page.rule(y)
    y = page.paragraph(y + 4, (
        "Capture rate = profit / perfect-foresight profit. Hour ranking = rank correlation between "
        "forecast and actual prices within a day (1 = perfect order). Robust: OLS beats naive by "
        f"{min(case_gain):.1%} to {max(case_gain):.1%} for batteries of 1, 2 and 4 hours and wear "
        "costs of 0, 10 and 20 EUR/MWh."
    ), size=8, color=MUTED, width=134)

    # ---- Charts ----------------------------------------------------------------
    y = page.picture(FIG_DIR / "04_battery_cumulative_profit.png", top=y + 4, width=342)
    y = page.picture(FIG_DIR / "05_battery_example_day.png", top=y + 3, width=342)

    # ---- Method and limitations ----------------------------------------------
    y += 3
    page.rule(y)
    page.text(LEFT, y + 5, "Method and limitations", size=8.5, weight="bold")
    y = page.paragraph(y + 18, (
        "Each day a linear program (scipy, HiGHS) chooses the 24 hourly charge and discharge volumes "
        "that maximise profit at the forecast prices; the plan is then paid at the actual prices. "
        "Battery: 90% round-trip efficiency, at most 1 cycle per day, starts and ends each day half "
        "full, wear cost 10 EUR per MWh sold. Limitations: day-ahead market only (no intraday or "
        "balancing income), no grid fees or taxes, price taker, hourly instead of 15-minute prices, "
        "fixed volumes instead of price-limited bids, each day planned on its own, one test year."
    ), size=8, color=MUTED, width=134)
    return page.fig, y


def main():
    out = OUT_DIR / "summary.pdf"
    with PdfPages(out) as pdf:
        for number, build in enumerate((forecast_page, battery_page), start=1):
            fig, y = build()
            pdf.savefig(fig, dpi=300)
            plt.close(fig)
            print(f"Page {number}: lowest text ends at {y:.0f} of {PAGE_H} points")
            if y > PAGE_H - 15:
                print("WARNING: the text runs off the page. Shorten the text or make the charts smaller.")
    print(f"Saved: {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
