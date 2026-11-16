"""Milestone B4: the two battery charts.

    python battery/charts.py        (after battery/backtest.py)

    outputs/figures/04_battery_cumulative_profit.png   profit building up over 2025, per forecast
    outputs/figures/05_battery_example_day.png         one typical day: prices and the battery plan
"""

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backtest import FORECASTS, MAIN, NAIVE, OUT_DIR, PERFECT, ROOT
from battery_lp import Battery

FIG_DIR = ROOT / "outputs" / "figures"

# Same look as src/evaluate.py: actual = black, OLS = blue, naive = orange.
# The palette was checked for colour-blind safety (blue, orange, aqua).
COLOUR = {PERFECT: "#0b0b0b", MAIN: "#2a78d6", NAIVE: "#eb6834", "ols_noweather": "#1baf7a"}
SHORT = {PERFECT: "Perfect foresight", MAIN: "OLS, forecast weather",
         NAIVE: "Naive: yesterday", "ols_noweather": "OLS, no weather"}
INK, MUTED, GRID, AXIS = "#0b0b0b", "#52514e", "#e1e0d9", "#c3c2b7"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 10,
    "axes.edgecolor": AXIS,
    "axes.labelcolor": MUTED,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
})


def quiet_frame(ax):
    """Light horizontal grid, no box."""
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def title_block(ax, title, subtitle):
    """Bold title on the left, with a grey subtitle of 1 or 2 lines under it."""
    lines = subtitle.count("\n") + 1
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold", pad=14 + 14 * lines)
    ax.text(0, 1.03, subtitle, transform=ax.transAxes, color=MUTED, fontsize=9.5,
            va="bottom", ha="left", linespacing=1.3)


def spread_labels(values, min_gap):
    """Move label positions apart so that they do not overlap. Keeps their order."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    positions = list(values)
    for below, above in zip(order, order[1:]):
        if positions[above] - positions[below] < min_gap:
            positions[above] = positions[below] + min_gap
    return positions


def chart_cumulative_profit(daily):
    """Chart 1: profit adding up day by day, one line per forecast."""
    cumulative = daily.cumsum() / 1000.0                    # thousand EUR
    days = pd.to_datetime(cumulative.index)
    total = cumulative.iloc[-1]

    fig, ax = plt.subplots(figsize=(9, 4.4))
    for column in (NAIVE, "ols_noweather", MAIN, PERFECT):   # draw the main lines last, on top
        ax.plot(days, cumulative[column], color=COLOUR[column], linewidth=2, label=SHORT[column])

    # Label the end of each line with its total, so the legend is not the only key.
    columns = list(FORECASTS)
    label_y = spread_labels([total[c] for c in columns], min_gap=3.4)
    label_x = days[-1] + pd.Timedelta(days=9)
    for column, y in zip(columns, label_y):
        ax.plot(days[-1], total[column], marker="o", markersize=6, color=COLOUR[column],
                markeredgecolor="white", markeredgewidth=1.2, clip_on=False, zorder=5)
        # A thin line ties each number to its dot, also when the number had to move up.
        ax.annotate(f"{total[column] * 1000:,.0f}", xy=(days[-1], total[column]), xytext=(label_x, y),
                    va="center", ha="left", color=INK, fontsize=9,
                    fontweight="bold" if column == MAIN else "normal", annotation_clip=False,
                    arrowprops={"arrowstyle": "-", "color": AXIS, "linewidth": 0.9,
                                "shrinkA": 1, "shrinkB": 4})

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.set_xlim(days[0], days[-1])
    ax.set_ylim(0, total.max() * 1.05)
    ax.set_ylabel("Cumulative profit (thousand EUR)")
    quiet_frame(ax)

    gain = (total[MAIN] - total[NAIVE]) * 1000
    title_block(
        ax,
        "Battery profit over 2025, by price forecast",
        "1 MW / 2 MWh battery on the Dutch day-ahead market. Planned on the forecast, paid at actual prices.\n"
        f"OLS earns {gain:,.0f} EUR more than the naive forecast and captures "
        f"{total[MAIN] / total[PERFECT]:.1%} of the perfect-foresight profit.",
    )
    handles, labels = ax.get_legend_handles_labels()
    # The lower right corner is empty, so the legend goes there (white box hides the grid lines).
    ax.legend(handles[::-1], labels[::-1], loc="lower right", frameon=True, facecolor="white",
              edgecolor="none", framealpha=1, fontsize=9, labelcolor=MUTED, handlelength=1.6,
              borderaxespad=1.0)
    fig.tight_layout()
    fig.subplots_adjust(right=0.91)                          # room for the end labels
    fig.savefig(FIG_DIR / "04_battery_cumulative_profit.png", dpi=200, facecolor="white")
    plt.close(fig)


def pick_typical_day(daily, schedules):
    """Choose the example day by a fixed rule, so it is not cherry-picked.

    Rule: of all normal 24-hour days in 2025, take the day whose profit with the OLS plan is the
    MEDIAN. Half of the days went better, half went worse.
    """
    hours = schedules.groupby("date").size()
    normal_days = daily.loc[hours[hours == 24].index, MAIN].sort_values()
    return normal_days.index[len(normal_days) // 2]


def chart_example_day(date, day, forecast, daily):
    """Chart 2: top = actual price and OLS forecast, bottom = what the battery does."""
    hours = day["hour"].to_numpy()
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(9, 5.6), sharex=True,
                                      gridspec_kw={"height_ratios": [1.5, 1], "hspace": 0.16})

    # Prices are constant within an hour, so draw them as steps. Each step is as wide as one
    # hour and sits right above the bar of that hour.
    edges = np.append(hours - 0.5, hours[-1] + 0.5)
    actual = day["price"].to_numpy()
    top.step(edges, np.append(forecast, forecast[-1]), where="post", color=COLOUR[MAIN],
             linewidth=2, label="OLS forecast")
    top.step(edges, np.append(actual, actual[-1]), where="post", color=COLOUR[PERFECT],
             linewidth=2, label="Actual price")
    if min(actual.min(), forecast.min()) < 0:
        top.axhline(0, color=AXIS, linewidth=1)
    top.set_ylabel("EUR/MWh")
    quiet_frame(top)
    top.legend(loc="best", frameon=True, facecolor="white", edgecolor="none", framealpha=1,
               fontsize=9, labelcolor=MUTED, handlelength=1.6, borderaxespad=0.8)

    # Sell (discharge) goes up, buy (charge) goes down. Same blue: it is the plan of the OLS forecast.
    bottom.bar(hours, day[f"discharge_{MAIN}"], width=0.7, color=COLOUR[MAIN])
    bottom.bar(hours, -day[f"charge_{MAIN}"], width=0.7, color=COLOUR[MAIN])
    bottom.axhline(0, color=AXIS, linewidth=1)
    bottom.set_ylim(-1.25, 1.25)
    bottom.set_yticks([-1, 0, 1])
    bottom.set_ylabel("MWh per hour")
    bottom.set_xlabel("Hour of day (Dutch local time)")
    bottom.set_xticks(range(0, 24, 2))
    bottom.set_xlim(-0.6, 23.6)
    quiet_frame(bottom)
    # Say what up and down mean, next to the y-axis and between the grid lines.
    bottom.text(1.008, 0.70, "Sell\n(discharge)", transform=bottom.transAxes, color=MUTED,
                fontsize=9, va="center", ha="left", linespacing=1.2)
    bottom.text(1.008, 0.30, "Buy\n(charge)", transform=bottom.transAxes, color=MUTED,
                fontsize=9, va="center", ha="left", linespacing=1.2)

    profit = daily.loc[date]
    title_block(
        top,
        f"A typical day: {pd.Timestamp(date):%A %d %B %Y}",
        "Top: the OLS forecast and the actual price. Bottom: the battery plan made with the OLS forecast.\n"
        f"Profit this day: {profit[MAIN]:.0f} EUR with this plan, {profit[PERFECT]:.0f} EUR with perfect "
        "foresight. It is the day with the median profit.",
    )
    fig.savefig(FIG_DIR / "05_battery_example_day.png", dpi=200, facecolor="white", bbox_inches="tight",
                pad_inches=0.15)
    plt.close(fig)


def main():
    battery = Battery()
    daily = pd.read_csv(OUT_DIR / "daily_profit.csv", index_col="date")
    schedules = pd.read_csv(OUT_DIR / "schedules.csv")
    forecasts = pd.read_csv(ROOT / "outputs" / "forecasts_test.csv")
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    chart_cumulative_profit(daily)

    date = pick_typical_day(daily, schedules)
    day = schedules[schedules["date"] == date]
    forecast = forecasts.loc[forecasts["date"] == date, MAIN].to_numpy()
    chart_example_day(date, day, forecast, daily)

    print(f"EXAMPLE DAY: {date} (median OLS-plan profit of the normal 24-hour days)")
    print(f"  profit: OLS plan {daily.loc[date, MAIN]:.2f}, naive plan {daily.loc[date, NAIVE]:.2f}, "
          f"perfect foresight {daily.loc[date, PERFECT]:.2f} EUR")
    sold = day[f"discharge_{MAIN}"].sum()
    print(f"  OLS plan: buys {day[f'charge_{MAIN}'].sum():.2f} MWh, sells {sold:.2f} MWh "
          f"({sold / battery.one_way_eff / battery.capacity_mwh:.2f} cycle)")
    print("Saved: outputs/figures/04_battery_cumulative_profit.png, outputs/figures/05_battery_example_day.png")


if __name__ == "__main__":
    main()
