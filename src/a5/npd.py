"""NPD lookup exactly as Doc 29 5th Ed. Vol 2 §4.2 (pp. 27-29).

- Power:    linear interpolation between tabulated powers (Eq. 4-3); outside the
            envelope, linear extrapolation from the first/last two powers.
- Distance: linear in log10(d) between tabulated distances (Eq. 4-4); outside the
            envelope, extrapolation from the first/last two distances (Eq. 4-5a/b).
- Floors:   P = max(P, 1 lb/engine) for CNT-in-lb aircraft, applied before extrapolation;
            d = max(d, 30 m) (recommended, configurable).
- Flags:    power extrapolation that moves the level more than 5 dB beyond the envelope
            edge is FLAGGED, never clipped.

This module deliberately does NOT apply impedance, atmospheric, duration, directivity
or lateral-attenuation adjustments: those depend on flight/weather state and belong to
the noise-model stage.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .constants import M_TO_FT

LOG = np.log10


def _interp_log_distance(dists: np.ndarray, levels: np.ndarray, d: np.ndarray) -> np.ndarray:
    """levels: (n_power, n_dist). d: (n,). Returns (n_power, n) levels at d (Eq. 4-4, 4-5a, 4-5b)."""
    x = LOG(dists)
    xq = LOG(d)
    # segment index i such that x[i] <= xq < x[i+1]; clamp to first/last segment => extrapolation from end pairs
    i = np.clip(np.searchsorted(x, xq, side="right") - 1, 0, len(x) - 2)
    x0, x1 = x[i], x[i + 1]
    w = (xq - x0) / (x1 - x0)
    return levels[:, i] + (levels[:, i + 1] - levels[:, i]) * w


def _interp_linear_power(powers: np.ndarray, levels_at_d: np.ndarray, p: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """levels_at_d: (n_power, n). Returns level at p (n,) and the level at the nearest envelope edge (n,)."""
    i = np.clip(np.searchsorted(powers, p, side="right") - 1, 0, len(powers) - 2)
    cols = np.arange(len(p))
    p0, p1 = powers[i], powers[i + 1]
    l0, l1 = levels_at_d[i, cols], levels_at_d[i + 1, cols]
    level = l0 + (l1 - l0) * (p - p0) / (p1 - p0)
    edge = np.where(p < powers[0], levels_at_d[0, cols], np.where(p > powers[-1], levels_at_d[-1, cols], level))
    return level, edge


@dataclass
class NPDPolicy:
    distance_floor_m: float = 30.0
    power_floor_lb_per_engine: float = 1.0
    power_extrapolation_warn_db: float = 5.0


class NPDLookup:
    """Lookup over a long-format NPD table: npd_id, noise_metric, op_mode, power_setting, distance_ft, level_db."""

    def __init__(self, npd_long: pd.DataFrame, policy: NPDPolicy | None = None,
                 power_kind_by_npd: dict[str, str] | None = None):
        self.policy = policy or NPDPolicy()
        self.power_kind_by_npd = power_kind_by_npd or {}
        self._curves: dict[tuple, tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
        for key, g in npd_long.groupby(["npd_id", "noise_metric", "op_mode"], sort=False):
            piv = g.pivot(index="power_setting", columns="distance_ft", values="level_db").sort_index().sort_index(axis=1)
            if piv.isna().any().any():
                raise ValueError(f"incomplete NPD grid for {key}")
            if len(piv.index) < 2:
                raise ValueError(f"NPD family {key} has fewer than 2 power settings; Doc 29 interpolation undefined")
            self._curves[key] = (piv.index.to_numpy(float), piv.columns.to_numpy(float), piv.to_numpy(float))

    def families(self) -> list[tuple]:
        return list(self._curves)

    def lookup(self, npd_id: str, noise_metric: str, op_mode: str, power, distance_ft) -> pd.DataFrame:
        key = (npd_id, noise_metric, op_mode)
        if key not in self._curves:
            raise KeyError(f"no NPD family {key}")
        powers, dists, levels = self._curves[key]
        p_in = np.atleast_1d(np.asarray(power, dtype=float))
        d_in = np.atleast_1d(np.asarray(distance_ft, dtype=float))
        p_in, d_in = np.broadcast_arrays(p_in, d_in)
        if np.isnan(p_in).any() or np.isnan(d_in).any():
            raise ValueError("NaN power or distance passed to NPD lookup")
        if (d_in <= 0).any():
            raise ValueError("non-positive slant distance passed to NPD lookup")

        p = p_in.copy()
        power_floored = np.zeros_like(p, dtype=bool)
        if self.power_kind_by_npd.get(npd_id, "CNT_LB_PER_ENGINE") == "CNT_LB_PER_ENGINE":
            power_floored = p < self.policy.power_floor_lb_per_engine
            p = np.maximum(p, self.policy.power_floor_lb_per_engine)
        floor_ft = self.policy.distance_floor_m * M_TO_FT
        distance_floored = d_in < floor_ft
        d = np.maximum(d_in, floor_ft)

        at_d = _interp_log_distance(dists, levels, d)
        level, edge = _interp_linear_power(powers, at_d, p)
        excess = np.abs(level - edge)
        return pd.DataFrame({
            "level_db": level,
            "power_used": p,
            "distance_used_ft": d,
            "power_floored": power_floored,
            "distance_floored": distance_floored,
            "power_extrapolated": (p < powers[0]) | (p > powers[-1]),
            "distance_extrapolated": (d < dists[0]) | (d > dists[-1]),
            "power_extrapolation_excess_db": excess,
            "power_extrapolation_warning": excess > self.policy.power_extrapolation_warn_db,
        })
