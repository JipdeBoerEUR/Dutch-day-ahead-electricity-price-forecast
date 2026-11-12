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

plt.rcParams["font.family"] = ["Segoe UI", "DejaVu Sans"]


def main():
    results = pd.read_csv(OUT_DIR / "results.csv").set_index("model")
    naive = results.loc["Naive: same hour yesterday"]
    ols = results.loc["OLS regression"]
    no_weather = results.loc["OLS without weather (check)"]

    fig = plt.figure(figsize=(PAGE_W / 72, PAGE_H / 72))

    def text(x, y, string, size=9.5, color=INK, weight="normal", align="left"):
        fig.text(x / PAGE_W, 1 - y / PAGE_H, string, fontsize=size, color=color,
                 fontweight=weight, ha=align, va="top", linespacing=1.4)

    def paragraph(y, string, size=9.5, color=INK, width=108):
        """Write wrapped text and return the y position just below it."""
        lines = textwrap.wrap(string, width=width)
        text(LEFT, y, "\n".join(lines), size=size, color=color)
        return y + len(lines) * size * 1.4

    def rule(y, color=RULE):
        fig.add_artist(Line2D([LEFT / PAGE_W, RIGHT / PAGE_W], [1 - y / PAGE_H] * 2,
                              color=color, linewidth=0.8))

    def picture(path, top, width=470):
        image = mpimg.imread(path)
        height = width * image.shape[0] / image.shape[1]
        left = (PAGE_W - width) / 2
        ax = fig.add_axes([left / PAGE_W, 1 - (top + height) / PAGE_H, width / PAGE_W, height / PAGE_H])
        ax.imshow(image, interpolation="none")
        ax.axis("off")
        return top + height

    # ---- Header ------------------------------------------------------------
    text(LEFT, 38, "Forecasting the Dutch day-ahead electricity price", size=17, weight="bold")
    text(LEFT, 64, AUTHOR, size=9.5, color=MUTED)
    rule(84)

    # ---- Question and answer -------------------------------------------------
    text(LEFT, 94, "Question", weight="bold")
    y = paragraph(108, "Can a simple OLS regression forecast tomorrow's hourly Dutch day-ahead price "
                       "better than a naive rule, on a year of data it has never seen?")

    text(LEFT, y + 6, "Answer", weight="bold")
    y = paragraph(y + 20, (
        f"Yes. On the 2025 test set, OLS lowers the mean absolute error from {naive['MAE']:.2f} to "
        f"{ols['MAE']:.2f} EUR/MWh ({ols['MAE_vs_yesterday_%']:.1f}%) against the best naive benchmark. "
        f"This uses actual weather in place of a weather forecast, so it is an upper bound. With no "
        f"weather inputs at all the gain is {abs(no_weather['MAE_vs_yesterday_%']):.1f}%. "
        f"A live forecast would land between the two."
    ))

    # ---- Results table -------------------------------------------------------
    y += 8
    text(LEFT, y, "Results on the 2025 test set (EUR/MWh, 8,760 hours)", weight="bold")
    y += 18
    columns = [(330, "MAE"), (390, "RMSE"), (468, "MAE vs best naive"), (RIGHT, "RMSE vs best naive")]
    text(LEFT, y, "Model", size=8.5, color=MUTED)
    for x, label in columns:
        text(x, y, label, size=8.5, color=MUTED, align="right")
    y += 14
    rule(y)

    for model, row in results.iterrows():
        is_main = model == "OLS regression"
        is_base = model == "Naive: same hour yesterday"
        weight = "bold" if is_main else "normal"
        y += 4
        text(LEFT, y, model, weight=weight)
        values = [
            f"{row['MAE']:.2f}",
            f"{row['RMSE']:.2f}",
            "–" if is_base else f"{row['MAE_vs_yesterday_%']:+.1f}%",
            "–" if is_base else f"{row['RMSE_vs_yesterday_%']:+.1f}%",
        ]
        for (x, _), value in zip(columns, values):
            text(x, y, value, weight=weight, align="right")
        y += 14
    y += 4
    rule(y)
    y = paragraph(y + 5, 'Negative % = lower error than "same hour yesterday". Model fitted once on '
                         "2023–2024 (17,376 hours); 2025 was never used for fitting or tuning.",
                  size=8, color=MUTED, width=128)

    # ---- Charts ----------------------------------------------------------------
    y = picture(FIG_DIR / "02_sample_week.png", top=y + 4)
    y = picture(FIG_DIR / "03_mae_by_hour.png", top=y + 2)

    # ---- Method and limitations ----------------------------------------------
    y += 4
    rule(y)
    text(LEFT, y + 6, "Method and limitations", size=8.5, weight="bold")
    y = paragraph(y + 19, (
        "OLS with hour, weekday and month dummies, the price yesterday and last week, and solar "
        "radiation, 100 m wind speed and temperature (average of 5 Dutch locations). "
        "Limitations: weather is actual, not forecast; one fixed fit with no rolling re-estimation; "
        "no gas, CO2, load or cross-border inputs; a linear model underestimates price spikes; one "
        "test year only; 15-minute prices (from Oct 2025) are averaged to hourly."
    ), size=8, color=MUTED, width=128)
    paragraph(y + 3, "Data: energy-charts.info (Fraunhofer ISE), bidding zone NL, and Open-Meteo "
                     "historical weather API. Both public, CC BY 4.0. Code: Python, pandas, statsmodels.",
              size=8, color=MUTED, width=128)

    out = OUT_DIR / "summary.pdf"
    fig.savefig(out, dpi=300)
    plt.close(fig)
    print(f"Saved: {out.relative_to(ROOT)}  (lowest text ends at {y:.0f} of {PAGE_H} points)")


if __name__ == "__main__":
    main()
