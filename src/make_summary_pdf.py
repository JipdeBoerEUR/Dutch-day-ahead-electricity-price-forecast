"""Milestone 6: build the 1-page PDF summary.

Run from the project folder (after src/evaluate.py):

    python src/make_summary_pdf.py

It reads the real numbers from outputs/results.csv and the two charts from
outputs/figures/, and writes outputs/summary.pdf (one A4 page).
"""

from pathlib import Path
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.image as mpimg
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import pandas as pd

AUTHOR = "Jip · BSc Econometrics & Operations Research, Erasmus University Rotterdam"

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"

# A4 page in points (1 point = 1/72 inch). We place everything in points from the top-left.
PAGE_W, PAGE_H = 595, 842
LEFT, RIGHT = 48, 547
INK, MUTED, RULE = "#0b0b0b", "#52514e", "#c3c2b7"

BEST_NAIVE = "Naive: same hour yesterday"
MAIN_MODEL = "OLS, forecast weather"

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]


def p_text(p):
    """Show a p-value the way a paper would."""
    if pd.isna(p):
        return "–"
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


def main():
    results = pd.read_csv(OUT_DIR / "results.csv").set_index("model")
    naive = results.loc[BEST_NAIVE]
    main_row = results.loc[MAIN_MODEL]
    actual = results.loc["OLS, actual weather (upper bound)"]
    no_weather = results.loc["OLS, no weather"]

    fig = plt.figure(figsize=(PAGE_W / 72, PAGE_H / 72))

    def text(x, y, string, size=9.5, color=INK, weight="normal", align="left"):
        fig.text(x / PAGE_W, 1 - y / PAGE_H, string, fontsize=size, color=color,
                 fontweight=weight, ha=align, va="top", linespacing=1.4)

    def paragraph(y, string, size=9.5, color=INK, width=114):
        """Write wrapped text and return the y position just below it."""
        lines = textwrap.wrap(string, width=width)
        text(LEFT, y, "\n".join(lines), size=size, color=color)
        return y + len(lines) * size * 1.4

    def rule(y, color=RULE):
        fig.add_artist(Line2D([LEFT / PAGE_W, RIGHT / PAGE_W], [1 - y / PAGE_H] * 2,
                              color=color, linewidth=0.8))

    def picture(path, top, width=415):
        image = mpimg.imread(path)
        height = width * image.shape[0] / image.shape[1]
        left = (PAGE_W - width) / 2
        ax = fig.add_axes([left / PAGE_W, 1 - (top + height) / PAGE_H, width / PAGE_W, height / PAGE_H])
        ax.imshow(image, interpolation="none")
        ax.axis("off")
        return top + height

    # ---- Header ------------------------------------------------------------
    text(LEFT, 34, "Forecasting the Dutch day-ahead electricity price", size=17, weight="bold")
    text(LEFT, 60, AUTHOR, size=9.5, color=MUTED)
    rule(79)

    # ---- Question and answer -------------------------------------------------
    text(LEFT, 87, "Question", weight="bold")
    y = paragraph(101, "Can a simple OLS regression forecast tomorrow's hourly Dutch day-ahead price "
                       "better than a naive rule, on a year of data it has never seen?")

    text(LEFT, y + 5, "Answer", weight="bold")
    y = paragraph(y + 19, (
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
    text(LEFT, y, "Results on the 2025 test set (EUR/MWh, 8,760 hours)", weight="bold")
    y += 17
    columns = [(262, "MAE"), (312, "RMSE"), (384, "MAE vs naive"), (458, "RMSE vs naive"),
               (505, "DM stat"), (RIGHT, "p-value")]
    text(LEFT, y, "Model", size=8.5, color=MUTED)
    for x, label in columns:
        text(x, y, label, size=8.5, color=MUTED, align="right")
    y += 14
    rule(y)

    for model, row in results.iterrows():
        is_base = model == BEST_NAIVE
        weight = "bold" if model == MAIN_MODEL else "normal"
        y += 3
        text(LEFT, y, model, weight=weight)
        values = [
            f"{row['MAE']:.2f}",
            f"{row['RMSE']:.2f}",
            "–" if is_base else f"{row['MAE_vs_yesterday_%']:+.1f}%",
            "–" if is_base else f"{row['RMSE_vs_yesterday_%']:+.1f}%",
            "–" if is_base else f"{row['DM_stat']:+.2f}",
            p_text(row["DM_p_value"]),
        ]
        for (x, _), value in zip(columns, values):
            text(x, y, value, weight=weight, align="right")
        y += 14
    y += 3
    rule(y)
    y = paragraph(y + 4, (
        'Negative % = lower error than "same hour yesterday". DM = Diebold-Mariano test against '
        '"same hour yesterday" (absolute-error loss, averaged per day, Newey-West standard errors); '
        "positive = more accurate. Model fitted once on 2023–2024; 2025 was never used for fitting."
    ), size=8, color=MUTED, width=134)

    # ---- Charts ----------------------------------------------------------------
    y = picture(FIG_DIR / "02_sample_week.png", top=y + 2)
    y = picture(FIG_DIR / "03_mae_by_hour.png", top=y + 1)

    # ---- Method and limitations ----------------------------------------------
    y += 3
    rule(y)
    text(LEFT, y + 5, "Method and limitations", size=8.5, weight="bold")
    y = paragraph(y + 18, (
        "OLS with hour, weekday and month dummies, lagged prices, and solar radiation, 100 m wind "
        "speed and temperature (average of 5 Dutch locations). Fitted on 2023–2024 with actual "
        "weather; in 2025 it is fed forecasts made 48 hours ahead (DWD ICON). Limitations: trained "
        "on actual weather, tested on forecasts from another weather model (wind 1.0 m/s high); one "
        "fixed fit; no gas, CO2, load or cross-border inputs; a linear model underestimates price "
        "spikes; one test year; 15-minute prices (from Oct 2025) averaged to hourly."
    ), size=8, color=MUTED, width=134)
    y = paragraph(y + 3, "Data: energy-charts.info (Fraunhofer ISE), bidding zone NL, and Open-Meteo "
                         "(historical weather and previous-runs forecasts). Public, CC BY 4.0. "
                         "Code: Python, pandas, statsmodels.",
                  size=8, color=MUTED, width=134)

    out = OUT_DIR / "summary.pdf"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"Saved: {out.relative_to(ROOT)}  (lowest text ends at {y:.0f} of {PAGE_H} points)")
    if y > PAGE_H - 15:
        print("WARNING: the text runs off the page. Shorten the text or make the charts smaller.")


if __name__ == "__main__":
    main()
