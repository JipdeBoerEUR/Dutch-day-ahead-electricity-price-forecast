"""Milestone 5: evaluation charts on the 2025 test set.

Run from the project folder (after src/model_ols.py):

    python src/evaluate.py

It reads outputs/forecasts_test.csv and makes two charts for the main model
(OLS with real weather forecasts) against the naive benchmark:

    outputs/figures/02_sample_week.png   forecast vs actual for one typical week
    outputs/figures/03_mae_by_hour.png   average error for each hour of the day
    outputs/mae_by_hour.csv              the numbers behind the second chart
"""

from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

from metrics import mae

TZ = "Europe/Amsterdam"
ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"
FIG_DIR = OUT_DIR / "figures"

# One colour per series, the same in every chart (checked for colour-blind safety).
COLOUR = {"actual": "#0b0b0b", "ols": "#2a78d6", "naive": "#eb6834"}
LABEL = {"actual": "Actual price", "ols": "OLS forecast", "naive": "Naive: same hour yesterday"}
INK, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
})


def style(ax, title, subtitle):
    """Quiet chart frame: light horizontal grid, no box, title on the left."""
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)
    lines = subtitle.count("\n") + 1          # leave room for a 1- or 2-line subtitle
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=14 + 14 * lines)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, color=MUTED, fontsize=9.5,
            va="bottom", ha="left", linespacing=1.3)
    # The legend sits above the plot, on the right, out of the way of the data.
    ax.legend(loc="lower right", bbox_to_anchor=(1.0, 1.03), ncol=3, frameon=False,
              fontsize=9, labelcolor=MUTED, handlelength=1.6, columnspacing=1.4,
              borderaxespad=0.2)


def pick_typical_week(df):
    """Choose the sample week by a fixed rule, so it is not cherry-picked.

    Rule: of all full Monday-Sunday weeks in 2025, take the one whose OLS error
    (MAE) is the MEDIAN. Half of the weeks went better, half went worse.
    """
    monday = df["local"].dt.normalize() - pd.to_timedelta(df["local"].dt.dayofweek, unit="D")
    weeks = df.groupby(monday).filter(lambda week: len(week) == 168)
    monday = monday.loc[weeks.index]
    weekly_mae = weeks.groupby(monday).apply(lambda week: mae(week["price"], week["ols"]))
    ranked = weekly_mae.sort_values()
    chosen = ranked.index[len(ranked) // 2]
    return weeks[monday == chosen], weekly_mae


def chart_sample_week(week):
    fig, ax = plt.subplots(figsize=(9, 3.9))
    ax.plot(week["local"], week["naive_d1"], color=COLOUR["naive"], linewidth=1.6, label=LABEL["naive"])
    ax.plot(week["local"], week["ols"], color=COLOUR["ols"], linewidth=2, label=LABEL["ols"])
    ax.plot(week["local"], week["price"], color=COLOUR["actual"], linewidth=2, label=LABEL["actual"])
    if week[["price", "ols", "naive_d1"]].min().min() < 0:
        ax.axhline(0, color=AXIS, linewidth=1)

    ax.xaxis.set_major_locator(mdates.DayLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%a %d %b"))
    ax.set_xlim(week["local"].iloc[0], week["local"].iloc[-1])
    ax.set_ylabel("EUR/MWh")

    first, last = week["local"].iloc[0], week["local"].iloc[-1]
    week_mae_ols = mae(week["price"], week["ols"])
    week_mae_naive = mae(week["price"], week["naive_d1"])
    style(
        ax,
        "Forecast vs actual price in a typical week",
        f"{first:%d %b} to {last:%d %b %Y}, the week with the median OLS error.\n"
        f"MAE this week: OLS {week_mae_ols:.1f}, naive {week_mae_naive:.1f} EUR/MWh.",
    )
    fig.tight_layout()
    fig.savefig(FIG_DIR / "02_sample_week.png", dpi=200, facecolor="white")
    plt.close(fig)


def chart_mae_by_hour(by_hour):
    fig, ax = plt.subplots(figsize=(9, 3.9))
    for key, column in (("naive", "naive_d1"), ("ols", "ols")):
        ax.plot(by_hour.index, by_hour[column], color=COLOUR[key], linewidth=2,
                marker="o", markersize=6.5, markeredgecolor="white", markeredgewidth=1.5,
                label=LABEL[key])

    ax.set_xticks(range(0, 24, 2))
    ax.set_xlim(-0.5, 23.5)
    ax.set_ylim(0, by_hour.max().max() * 1.12)
    ax.set_xlabel("Hour of day (Dutch local time)")
    ax.set_ylabel("MAE (EUR/MWh)")
    style(
        ax,
        "Forecast error by hour of day, 2025 test set",
        "Mean absolute error per hour. Lower is better. OLS uses 48-hour weather forecasts.",
    )
    fig.tight_layout()
    fig.savefig(FIG_DIR / "03_mae_by_hour.png", dpi=200, facecolor="white")
    plt.close(fig)


def main():
    df = pd.read_csv(OUT_DIR / "forecasts_test.csv")
    # The charts show the MAIN model: OLS fed with real weather forecasts.
    df = df.rename(columns={"ols_fc": "ols"})
    # Dutch clock time, for the x-axis of the week chart.
    df["local"] = pd.to_datetime(df["time_utc"], utc=True).dt.tz_convert(TZ).dt.tz_localize(None)
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    # ---- Chart 1: one typical week -----------------------------------------
    week, weekly_mae = pick_typical_week(df)
    chart_sample_week(week)

    print("=" * 60)
    print("EVALUATION on the 2025 test set")
    print("=" * 60)
    print(f"SAMPLE WEEK: {week['date'].iloc[0]} to {week['date'].iloc[-1]}")
    print(f"  rule: median OLS error out of {len(weekly_mae)} full weeks")
    print(f"  MAE this week: OLS {mae(week['price'], week['ols']):.2f}"
          f"   naive {mae(week['price'], week['naive_d1']):.2f}")
    print(f"  best week OLS MAE {weekly_mae.min():.2f}   worst week {weekly_mae.max():.2f}")

    # ---- Chart 2: error by hour of day -------------------------------------
    errors = pd.DataFrame({
        "hour": df["hour"],
        "naive_d1": (df["price"] - df["naive_d1"]).abs(),
        "ols": (df["price"] - df["ols"]).abs(),
    })
    by_hour = errors.groupby("hour").mean()
    chart_mae_by_hour(by_hour)

    table = by_hour.copy()
    table["ols_vs_naive_%"] = (table["ols"] / table["naive_d1"] - 1) * 100
    table.round(2).to_csv(OUT_DIR / "mae_by_hour.csv")

    print("\nMAE BY HOUR OF DAY (EUR/MWh)")
    print(table.round(1).to_string())
    wins = int((table["ols"] < table["naive_d1"]).sum())
    print(f"\nOLS is better than the naive forecast in {wins} of 24 hours.")
    print(f"  OLS is best at hour {table['ols'].idxmin()} (MAE {table['ols'].min():.1f})"
          f" and worst at hour {table['ols'].idxmax()} (MAE {table['ols'].max():.1f}).")

    print("\nSaved: outputs/figures/02_sample_week.png, outputs/figures/03_mae_by_hour.png,"
          " outputs/mae_by_hour.csv")


if __name__ == "__main__":
    main()
