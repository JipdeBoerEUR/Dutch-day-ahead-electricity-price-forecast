"""Error metrics, used by every model so the comparison is fair."""

import numpy as np


def mae(actual, forecast):
    """Mean Absolute Error: the average size of the miss, in EUR/MWh."""
    return float(np.mean(np.abs(actual - forecast)))


def rmse(actual, forecast):
    """Root Mean Squared Error: like MAE, but big misses count extra."""
    return float(np.sqrt(np.mean((actual - forecast) ** 2)))
