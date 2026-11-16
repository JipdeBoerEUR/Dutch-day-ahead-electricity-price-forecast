"""Battery model: plan one day with a linear program, then settle it against real prices.

Two functions do all the work:

    optimise_day(prices, battery)   -> the best charge/discharge plan for these prices
    settle(plan, actual_prices, battery) -> the money this plan really makes

The plan is made with a price FORECAST. The money is counted with the ACTUAL prices.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import linprog


@dataclass(frozen=True)
class Battery:
    """All battery settings in one place. Change them here or per run."""

    power_mw: float = 1.0               # max charge or discharge power
    duration_h: float = 2.0             # hours of full power -> capacity = power x duration
    round_trip_eff: float = 0.90        # energy out / energy in over a full cycle
    max_cycles_per_day: float = 1.0     # 1 cycle = emptying the full capacity once
    start_soc: float = 0.50             # state of charge at the start AND end of each day
    degradation_eur_mwh: float = 10.0   # wear cost per MWh delivered to the grid

    @property
    def capacity_mwh(self):
        return self.power_mw * self.duration_h

    @property
    def one_way_eff(self):
        # The 90% loss is split evenly: sqrt(0.9) when charging, sqrt(0.9) when discharging.
        return float(np.sqrt(self.round_trip_eff))


def optimise_day(prices, battery=Battery()):
    """Find the charge/discharge plan that earns the most at the given hourly prices.

    Variables, one of each per hour t (hours last 1 h, so MW and MWh are the same number):
        charge[t]     MWh bought from the grid
        discharge[t]  MWh sold to the grid
        soc[t]        MWh stored in the battery at the END of hour t

    Returns a dict with those three arrays and `expected_profit` (profit at the given prices).
    """
    prices = np.asarray(prices, dtype=float)
    n = len(prices)                      # 24 on a normal day, 23 or 25 on clock-change days
    eff = battery.one_way_eff
    cap = battery.capacity_mwh
    start = battery.start_soc * cap

    # Order of the variables in the vector x: [charge (n), discharge (n), soc (n)]
    i_charge = np.arange(n)
    i_discharge = n + np.arange(n)
    i_soc = 2 * n + np.arange(n)

    # OBJECTIVE. linprog minimises, so we minimise MINUS the profit.
    #   profit = sum price*discharge - sum price*charge - degradation*discharge
    cost = np.zeros(3 * n)
    cost[i_charge] = prices
    cost[i_discharge] = -(prices - battery.degradation_eur_mwh)

    # CONSTRAINT 1 - energy balance (one equation per hour):
    #   soc[t] = soc[t-1] + eff*charge[t] - discharge[t]/eff
    # Charging 1 MWh stores only 0.949 MWh. Selling 1 MWh takes 1.054 MWh out of the battery.
    balance = np.zeros((n, 3 * n))
    balance_rhs = np.zeros(n)
    for t in range(n):
        balance[t, i_soc[t]] = 1.0
        balance[t, i_charge[t]] = -eff
        balance[t, i_discharge[t]] = 1.0 / eff
        if t == 0:
            balance_rhs[t] = start       # soc before the first hour = 50%
        else:
            balance[t, i_soc[t - 1]] = -1.0

    # CONSTRAINT 2 - one inverter: charge[t] + discharge[t] <= power.
    # This makes charging and discharging in the same hour unattractive.
    inverter = np.zeros((n, 3 * n))
    for t in range(n):
        inverter[t, i_charge[t]] = 1.0
        inverter[t, i_discharge[t]] = 1.0
    inverter_rhs = np.full(n, battery.power_mw)

    # CONSTRAINT 3 - cycle limit: energy taken OUT of the battery in a day <= cycles x capacity.
    cycles = np.zeros((1, 3 * n))
    cycles[0, i_discharge] = 1.0 / eff
    cycles_rhs = np.array([battery.max_cycles_per_day * cap])

    # CONSTRAINTS 4, 5, 6 are simple bounds on each variable:
    #   4. power:    0 <= charge[t], discharge[t] <= power
    #   5. capacity: 0 <= soc[t] <= capacity
    #   6. end of day: soc[last hour] = 50% (same as the start)
    bounds = [(0.0, battery.power_mw)] * (2 * n) + [(0.0, cap)] * (n - 1) + [(start, start)]

    result = linprog(
        cost,
        A_ub=np.vstack([inverter, cycles]),
        b_ub=np.concatenate([inverter_rhs, cycles_rhs]),
        A_eq=balance,
        b_eq=balance_rhs,
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        raise RuntimeError(f"LP did not solve: {result.message}")

    # Remove solver noise such as 1e-15 or -0.0.
    x = np.where(np.abs(result.x) < 1e-9, 0.0, result.x)
    return {
        "charge": x[i_charge],
        "discharge": x[i_discharge],
        "soc": x[i_soc],
        "expected_profit": -result.fun,
    }


def settle(plan, actual_prices, battery=Battery()):
    """Money the plan really makes at the actual prices (EUR), after the degradation cost."""
    actual_prices = np.asarray(actual_prices, dtype=float)
    revenue = np.sum(actual_prices * plan["discharge"])
    charging_cost = np.sum(actual_prices * plan["charge"])
    wear = battery.degradation_eur_mwh * np.sum(plan["discharge"])
    return float(revenue - charging_cost - wear)


def check_plan(plan, battery=Battery(), tol=1e-6):
    """Check that a plan obeys every battery rule. Returns a dict of True/False per rule."""
    eff = battery.one_way_eff
    cap = battery.capacity_mwh
    start = battery.start_soc * cap
    charge, discharge, soc = plan["charge"], plan["discharge"], plan["soc"]

    soc_before = np.concatenate([[start], soc[:-1]])
    return {
        "energy balance holds": bool(np.allclose(soc, soc_before + eff * charge - discharge / eff, atol=tol)),
        "power within limit": bool((charge + discharge <= battery.power_mw + tol).all()
                                   and (charge >= -tol).all() and (discharge >= -tol).all()),
        "soc between 0 and capacity": bool((soc >= -tol).all() and (soc <= cap + tol).all()),
        "ends at start level": bool(abs(soc[-1] - start) <= tol),
        "at most the allowed cycles": bool(np.sum(discharge) / eff <= battery.max_cycles_per_day * cap + tol),
        "never charges and discharges together": bool((np.minimum(charge, discharge) <= tol).all()),
    }
