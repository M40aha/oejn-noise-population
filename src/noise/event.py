"""Single-event levels (Doc 29 Vol 2 Eq. 4-10 / 4-11) of one flight path at many receptors.

L_E = 10 lg sum 10^(L_E,seg/10) over segments; L_max = max over segments.
NPD curves are taken from the A5 release (NPDLookup interpolation rules, Eq. 4-3..4-5, floors) with the
Appendix D atmospheric increment dL(d_i) added to the tabulated levels of both metrics, and the Method A
substitution adjustment delta (A5 mapping) added to every level.
"""
from __future__ import annotations

import numpy as np

from a5.npd import NPDLookup
from a5.constants import M_TO_FT
from . import doc29 as D


class AdjustedNPD:
    """Fast NPD interpolation for one (npd_id, op_mode), levels += dL(d_i) (Appendix D)."""

    def __init__(self, lookup: NPDLookup, npd_id: str, op_mode: str = "D", dL=None, power_kind="CNT_LB_PER_ENGINE"):
        self.c = {}
        for metric in ("SEL", "LAmax"):
            powers, dists, levels = lookup._curves[(npd_id, metric, op_mode)]
            add = np.zeros(len(dists)) if dL is None else np.asarray(dL, float)
            self.c[metric] = (powers, dists, levels + add[None, :])
        self.floor_ft = lookup.policy.distance_floor_m * M_TO_FT
        self.p_floor = lookup.policy.power_floor_lb_per_engine if power_kind == "CNT_LB_PER_ENGINE" else -np.inf

    def __call__(self, metric, P, d_ft):
        powers, dists, levels = self.c[metric]
        p, d = np.broadcast_arrays(np.atleast_1d(np.asarray(P, float)), np.atleast_1d(np.asarray(d_ft, float)))
        p = np.maximum(p, self.p_floor)
        d = np.maximum(d, self.floor_ft)
        # same arithmetic as NPDLookup (Eq. 4-3..4-5: linear in P, linear in lg d, end-pair extrapolation), evaluated
        # only on the two bracketing power rows instead of all rows
        x = np.log10(dists)
        xq = np.log10(d)
        j = np.clip(np.searchsorted(x, xq, side="right") - 1, 0, len(x) - 2)
        wd = (xq - x[j]) / (x[j + 1] - x[j])
        i = np.clip(np.searchsorted(powers, p, side="right") - 1, 0, len(powers) - 2)
        l0 = levels[i, j] + (levels[i, j + 1] - levels[i, j]) * wd
        l1 = levels[i + 1, j] + (levels[i + 1, j + 1] - levels[i + 1, j]) * wd
        return l0 + (l1 - l0) * (p - powers[i]) / (powers[i + 1] - powers[i])

    def sel(self, P, d):
        return self("SEL", P, d)

    def lmax(self, P, d):
        return self("LAmax", P, d)


def _seg_hdist(seg, rx, ry):
    """Horizontal distance from receptors to the segment's ground projection."""
    x1, y1, x2, y2 = seg.x1, seg.y1, seg.x2, seg.y2
    gx, gy = x2 - x1, y2 - y1
    L2 = gx * gx + gy * gy
    t = np.clip(((rx - x1) * gx + (ry - y1) * gy) / L2, 0, 1) if L2 > 0 else 0.0
    return np.hypot(rx - (x1 + t * gx), ry - (y1 + t * gy))


def event_levels(segs, rx, ry, rz, npd: AdjustedNPD, installation: str, engine: str = "Jet",
                 impedance_db: float = 0.0, delta_db: float = 0.0, prune_ft: float | None = None):
    """SEL and LAmax of one flight at receptors (rx, ry, rz in ft, frame of the segments).
    prune_ft: receptors farther than this (horizontally) from a segment get no contribution from it.
    Returns (sel, lmax) with -inf where no segment contributed."""
    rx, ry, rz = (np.asarray(a, float) for a in (rx, ry, rz))
    energy = np.zeros(rx.shape)
    lmax = np.full(rx.shape, -np.inf)
    for s in segs.itertuples(index=False):
        if prune_ft is not None:
            idx = np.nonzero(_seg_hdist(s, rx, ry) <= prune_ft)[0]
            if idx.size == 0:
                continue
        else:
            idx = slice(None)
        g = D.segment_geometry((s.x1, s.y1, s.z1), (s.x2, s.y2, s.z2), rx[idx], ry[idx], rz[idx], bank_deg=s.bank)
        gr = s.ground_roll if s.ground_roll else None
        P = D.interp_power(s.P1, s.P2, g["q"], g["lam"], g["pos"])
        dV = D.duration_correction(s.V1, s.V2, g["q"], g["lam"], g["pos"], gr is not None)
        r = D.segment_levels(g, P, dV, npd.sel, npd.lmax, installation, engine, gr, impedance_db, delta_db)
        energy[idx] += 10.0 ** (r["sel"] / 10.0)
        lmax[idx] = np.maximum(lmax[idx], r["lmax"])
    with np.errstate(divide="ignore"):
        sel = 10.0 * np.log10(energy)
    return sel, lmax
