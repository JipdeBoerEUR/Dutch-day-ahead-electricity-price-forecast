"""Milestone B1: check the one-day LP against answers worked out by hand.

    python battery/check_one_day.py

Four checks:
  A. Toy day, battery without losses  -> profit must be exactly 160 EUR.
  B. Same toy day, real battery       -> profit must match the hand formula (125.35 EUR).
  C. Flat prices                      -> the battery must do nothing (profit 0).
  D. A real day in 2025               -> the plan must obey every battery rule.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from battery_lp import Battery, check_plan, optimise_day, settle

ROOT = Path(__file__).resolve().parent.parent
FORECASTS = ROOT / "outputs" / "forecasts_test.csv"
REAL_DAY = "2025-05-14"


def toy_prices():
    """50 EUR/MWh all day. One cheap hour (3), two expensive hours (19 and 20)."""
    prices = np.full(24, 50.0)
    prices[3] = 10.0
    prices[19] = 120.0
    prices[20] = 100.0
    return prices


def print_plan(prices, plan):
    """Print only the hours in which the battery does something."""
    table = pd.DataFrame({
        "hour": np.arange(len(prices)),
        "price": prices,
        "charge_mwh": plan["charge"],
        "discharge_mwh": plan["discharge"],
        "soc_mwh": plan["soc"],
    })
    active = table[(table["charge_mwh"] > 0) | (table["discharge_mwh"] > 0)]
    print(active.round(3).to_string(index=False))


def report(name, lp_value, hand_value):
    ok = abs(lp_value - hand_value) < 0.01
    print(f"  LP profit {lp_value:8.2f} EUR | by hand {hand_value:8.2f} EUR | {'OK' if ok else 'WRONG'}")
    return ok


def main():
    all_ok = True
    prices = toy_prices()

    # --- A. No losses, no degradation cost: every number is round. ---------------------------
    print("\nA. Toy day, battery WITHOUT losses (efficiency 100%, degradation 0)")
    ideal = Battery(round_trip_eff=1.0, degradation_eur_mwh=0.0)
    plan = optimise_day(prices, ideal)
    print_plan(prices, plan)
    # By hand: start half full (1 MWh). Buy 1 at 10 -> full. Sell 1 at 120 and 1 at 100 -> empty
    # (that is the one allowed cycle). Buy 1 back at 50 to end half full.
    by_hand = -10 + 120 + 100 - 50
    all_ok &= report("A", settle(plan, prices, ideal), by_hand)

    # --- B. Real battery: 90% round trip, 10 EUR/MWh degradation. -----------------------------
    print("\nB. Same toy day, REAL battery (90% round trip, degradation 10 EUR/MWh)")
    real = Battery()
    e = real.one_way_eff                       # 0.9487
    plan = optimise_day(prices, real)
    print_plan(prices, plan)
    # By hand, same idea, now with losses:
    sold_at_120 = 1.0                          # full power; takes 1/e = 1.054 MWh out of the battery
    sold_at_100 = e * (2.0 - 1.0 / e)          # the rest of the 2 MWh cycle -> 0.897 MWh sold
    bought_at_10 = 1.0                         # full power in the cheap hour
    bought_at_50 = 2.0 / e - 1.0               # the 2 MWh must be put back: 2/e bought in total
    sold = sold_at_120 + sold_at_100
    by_hand = (120 * sold_at_120 + 100 * sold_at_100
               - 10 * bought_at_10 - 50 * bought_at_50
               - real.degradation_eur_mwh * sold)
    all_ok &= report("B", settle(plan, prices, real), by_hand)

    # --- C. Flat prices: trading only loses money, so the best plan is to do nothing. ---------
    print("\nC. Flat prices (50 EUR/MWh every hour), real battery")
    flat = np.full(24, 50.0)
    plan = optimise_day(flat, real)
    all_ok &= report("C", settle(plan, flat, real), 0.0)

    # --- D. A real day with perfect foresight: does the plan obey every rule? -----------------
    print(f"\nD. Real day {REAL_DAY}, perfect foresight, real battery")
    data = pd.read_csv(FORECASTS)
    day = data[data["date"] == REAL_DAY]
    actual = day["price"].to_numpy()
    plan = optimise_day(actual, real)
    print_plan(actual, plan)
    print(f"  Profit: {settle(plan, actual, real):.2f} EUR")
    for rule, passed in check_plan(plan, real).items():
        print(f"  {'OK   ' if passed else 'WRONG'} {rule}")
        all_ok &= passed

    print("\nALL CHECKS PASSED" if all_ok else "\nSOME CHECKS FAILED")
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
