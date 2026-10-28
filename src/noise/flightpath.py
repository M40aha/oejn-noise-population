"""Doc 29 Vol 2 Chapter 3 flight-path construction from observed (ADS-B) trajectories.

Doc 29 §3.6.1: "When matching flight profile segments to radar data (flight path analysis), all end-point
distances, heights, speeds and bank angles are determined directly from the data; only the power settings have
to be calculated using the performance equations."

Pipeline for one departure (all geometry in feet, local horizontal frame; z = height above the aerodrome plane):
  1. observations -> airborne track points (heights, ground speed, CAS, pressure altitude)    [prepare_track]
  2. lift-off point from the first airborne points (straight-line climb fit back to z = 0)    [find_liftoff]
  3. take-off ground roll from the start of roll (SOR) to lift-off, Eq. 3-3a..3-3e             [ground_roll_nodes]
  4. initial-climb sub-segmentation of the lift-off -> first observed point segment, Eq. 3-4   [initial_climb_nodes]
  5. observed airborne points, thinned only where Doc 29 allows (§3.6.5 speed change <= 20 kt,
     §3.6.7 points < 10 m apart) and bounded segment lengths                                    [thin_track]
  6. power at every node from the ANP jet coefficients (B-9/B-10/B-11), take-off rating below the
     ANP cut-back height, climb rating above                                                     [assign_power]
  7. bank angle from the observed turn rate, Eq. B-14                                           [bank_angle]
The output is a node table; consecutive nodes are the Doc 29 segments.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

FT = 0.3048
KT_TO_FTS = 1.6878098571
G_FTS2 = 32.17405
SOURCE_MIN_Z_FT = 1.0 / FT                     # Doc 29 §3.5: source at least 1 m above the aerodrome level
Z_PRIME_M = np.array([18.9, 41.5, 68.3, 102.1, 147.5, 214.9, 334.9, 609.6, 1289.6])   # §3.6.4 height set (metres,
Z_PRIME_FT = Z_PRIME_M / FT                                                           #  as in the worked example)


@dataclass
class PathPolicy:
    min_seg_ft_low: float = 500.0       # target node spacing below 1,500 ft (keeps lateral-attenuation steps small)
    min_seg_ft_mid: float = 1000.0      # 1,500-4,231 ft
    min_seg_ft_high: float = 3000.0     # above 4,231 ft
    max_speed_step_kt: float = 10.0     # node kept when speed changed by this much (=> segments within §3.6.5)
    max_heading_step_deg: float = 5.0   # node kept when the track turned by this much
    max_gap_s: float = 60.0             # an observation gap above this splits nothing but is flagged
    liftoff_fit_max_z_ft: float = 1500.0
    liftoff_fit_points: int = 6
    liftoff_min_ft: float = 1500.0      # plausibility window for the lift-off distance from SOR
    height_smoothing_points: int = 5    # centred running median on heights (25-ft altitude quantisation)
    bank_smoothing_s: float = 20.0      # turn-rate smoothing window
    max_bank_deg: float = 35.0


# --------------------------------------------------------------------------------------------- step 1
def prepare_track(obs: pd.DataFrame, policy: PathPolicy) -> pd.DataFrame:
    """obs columns (already in the local frame): t_s, x_ft, y_ft, z_ft, gs_kt, on_ground,
    optional: cas_kt, h_press_ft. Returns airborne points sorted in time with smoothed heights."""
    o = obs.sort_values("t_s").drop_duplicates("t_s").reset_index(drop=True)
    o = o[np.isfinite(o.x_ft) & np.isfinite(o.y_ft)]
    air = o[(~o.on_ground.fillna(False).astype(bool)) & np.isfinite(o.z_ft)].copy()
    if policy.height_smoothing_points > 1 and len(air) >= policy.height_smoothing_points:
        air["z_ft"] = air.z_ft.rolling(policy.height_smoothing_points, center=True, min_periods=1).median()
    # ground speed: observed; where missing, from consecutive positions (flagged)
    air["gs_source"] = np.where(np.isfinite(air.gs_kt), "observed", "derived")
    if (~np.isfinite(air.gs_kt)).any():
        dt = air.t_s.diff().bfill()
        ds = np.hypot(air.x_ft.diff(), air.y_ft.diff()).bfill()
        air.loc[~np.isfinite(air.gs_kt), "gs_kt"] = (ds / dt / KT_TO_FTS)[~np.isfinite(air.gs_kt)]
    return air.reset_index(drop=True)


# --------------------------------------------------------------------------------------------- step 2
def find_liftoff(air: pd.DataFrame, sor_xy, axis_u, tora_ft: float, policy: PathPolicy) -> dict:
    """Lift-off distance from SOR along the runway axis by a straight-line fit z(s) through the first airborne
    points below liftoff_fit_max_z_ft (Doc 29 §3.2: fit straight segments to the data), clamped to
    [liftoff_min_ft, TORA]. Returns s_lo_ft, V_lo_kt (ground speed interpolated at lift-off) and flags."""
    s = (air.x_ft - sor_xy[0]) * axis_u[0] + (air.y_ft - sor_xy[1]) * axis_u[1]
    low = air[(air.z_ft <= policy.liftoff_fit_max_z_ft) & (s > 0)].head(policy.liftoff_fit_points)
    flags = []
    s_lo = np.nan
    if len(low) >= 2:
        sl = s[low.index].to_numpy()
        zl = low.z_ft.to_numpy()
        b, a = np.polyfit(sl, zl, 1)
        if b > 0:
            s_lo = -a / b
    if not np.isfinite(s_lo):
        flags.append("liftoff_fit_failed")
        s_lo = float(s[air.index[0]]) if len(air) else tora_ft
    if s_lo < policy.liftoff_min_ft:
        flags.append("liftoff_clamped_min")
        s_lo = policy.liftoff_min_ft
    if s_lo > tora_ft:
        flags.append("liftoff_clamped_tora")
        s_lo = tora_ft
    first = air.iloc[0] if len(air) else None
    v_lo = float(low.gs_kt.iloc[0]) if len(low) else (float(first.gs_kt) if first is not None else np.nan)
    if len(low) >= 2 and np.isfinite(low.gs_kt).sum() >= 2:   # extrapolate GS^2 linearly in distance to lift-off
        sl = s[low.index].to_numpy()
        g2 = low.gs_kt.to_numpy() ** 2
        k = np.isfinite(g2)
        if k.sum() >= 2 and np.ptp(sl[k]) > 0:
            bb, aa = np.polyfit(sl[k], g2[k], 1)
            v = aa + bb * s_lo
            if v > 0 and abs(np.sqrt(v) - v_lo) < 40:
                v_lo = float(np.sqrt(v))
    return {"s_lo_ft": float(s_lo), "v_lo_kt": v_lo, "s_obs_ft": s.to_numpy(), "flags": flags}


# --------------------------------------------------------------------------------------------- step 3
def ground_roll_nodes(sor_xy, axis_u, s_lo_ft: float, v_lo_kt: float) -> pd.DataFrame:
    """Eq. 3-3a..d: n = int(1 + V_TO/10) (V in m/s), segment k ends at s_TO (k/n)^2, speed k V_TO / n.
    Power is assigned later with the constant increment of Eq. 3-3e (linear in k)."""
    v_ms = v_lo_kt * KT_TO_FTS * FT
    n = int(1 + v_ms / 10.0)
    k = np.arange(n + 1)
    s = s_lo_ft * (k / n) ** 2
    return pd.DataFrame({"x_ft": sor_xy[0] + s * axis_u[0], "y_ft": sor_xy[1] + s * axis_u[1],
                         "z_ft": SOURCE_MIN_Z_FT, "V_kt": v_lo_kt * k / n, "roll_k": k, "roll_n": n,
                         "kind": "roll", "s_ft": s})


# --------------------------------------------------------------------------------------------- step 4
def initial_climb_nodes(lo: dict, first: dict) -> pd.DataFrame:
    """Eq. 3-4 with k = 1: heights z_i = z_e z'_i / z'_N between lift-off and the first observed point (height
    z_e); z linear with distance (3-2a), V by 3-2b. Power at inserted points is assigned later (3-2d)."""
    ze = min(first["z_ft"], Z_PRIME_FT[-1])
    if first["z_ft"] <= SOURCE_MIN_Z_FT + 1:
        return pd.DataFrame(columns=["x_ft", "y_ft", "z_ft", "V_kt", "kind"])
    nidx = int(np.argmin(np.abs(Z_PRIME_FT - ze)))
    zi = ze * Z_PRIME_FT[: nidx + 1] / Z_PRIME_FT[nidx]
    zi = zi[(zi > SOURCE_MIN_Z_FT) & (zi < first["z_ft"] - 1e-6)]
    z0 = SOURCE_MIN_Z_FT
    f = (zi - z0) / (first["z_ft"] - z0)
    x = lo["x_ft"] + f * (first["x_ft"] - lo["x_ft"])
    y = lo["y_ft"] + f * (first["y_ft"] - lo["y_ft"])
    V = np.sqrt(lo["V_kt"] ** 2 + f * (first["V_kt"] ** 2 - lo["V_kt"] ** 2))
    return pd.DataFrame({"x_ft": x, "y_ft": y, "z_ft": zi, "V_kt": V, "kind": "climb_inserted", "f": f})


# --------------------------------------------------------------------------------------------- step 5
def thin_track(air: pd.DataFrame, policy: PathPolicy) -> pd.DataFrame:
    """Keep the first and last points, and every point where distance since the last kept point reaches the
    height-dependent spacing, or the speed / track changed by the policy step. Points closer than 10 m to
    the previous kept point are dropped (§3.6.7)."""
    if len(air) <= 2:
        return air.copy()
    xs, ys, zs = air.x_ft.to_numpy(), air.y_ft.to_numpy(), air.z_ft.to_numpy()
    vs = air.gs_kt.to_numpy()
    trk = np.degrees(np.arctan2(np.gradient(xs), np.gradient(ys)))
    keep = [0]
    for i in range(1, len(air) - 1):
        j = keep[-1]
        d = np.sqrt((xs[i] - xs[j]) ** 2 + (ys[i] - ys[j]) ** 2 + (zs[i] - zs[j]) ** 2)
        if d < 10.0 / FT:
            continue
        lim = policy.min_seg_ft_low if zs[i] < 1500 else (policy.min_seg_ft_mid if zs[i] < 4231 else policy.min_seg_ft_high)
        dh = abs((trk[i] - trk[j] + 180) % 360 - 180)
        nxt = i + 1
        dv_next = abs(vs[nxt] - vs[j]) if np.isfinite(vs[nxt]) and np.isfinite(vs[j]) else 0.0
        d_next = np.sqrt((xs[nxt] - xs[j]) ** 2 + (ys[nxt] - ys[j]) ** 2 + (zs[nxt] - zs[j]) ** 2)
        dh_next = abs((trk[nxt] - trk[j] + 180) % 360 - 180)
        # keep i if moving on to i+1 would exceed a limit
        if d_next > lim or dv_next > policy.max_speed_step_kt or dh_next > policy.max_heading_step_deg or dh > policy.max_heading_step_deg:
            keep.append(i)
    keep.append(len(air) - 1)
    return air.iloc[sorted(set(keep))].reset_index(drop=True)


# --------------------------------------------------------------------------------------------- step 7
def bank_angle(nodes: pd.DataFrame, air: pd.DataFrame, policy: PathPolicy) -> np.ndarray:
    """Eq. B-14 rearranged for observed data: tan(eps) = V * omega / g (V ground speed ft/s, omega turn rate rad/s);
    turn rate from the observed track (smoothed); positive = right turn (starboard wing down)."""
    if len(air) < 3:
        return np.zeros(len(nodes))
    t = air.t_s.to_numpy()
    trk = np.unwrap(np.arctan2(np.gradient(air.x_ft.to_numpy()), np.gradient(air.y_ft.to_numpy())))
    w = max(1, int(round(policy.bank_smoothing_s / max(np.median(np.diff(t)), 0.5))))
    trk_s = pd.Series(trk).rolling(w, center=True, min_periods=1).mean().to_numpy()
    omega = np.gradient(trk_s, t)
    v = air.gs_kt.to_numpy() * KT_TO_FTS
    eps = np.degrees(np.arctan(v * omega / G_FTS2))
    eps = np.clip(eps, -policy.max_bank_deg, policy.max_bank_deg)
    return np.interp(nodes.t_s.to_numpy(), t, eps, left=0.0, right=0.0)


# --------------------------------------------------------------------------------------------- assembly
def build_path(obs: pd.DataFrame, sor_xy, axis_u, tora_ft: float, power_fn, cutback_ft: float,
               policy: PathPolicy | None = None) -> tuple[pd.DataFrame, dict]:
    """obs: local-frame observations (see prepare_track) with optional cas_kt / h_press_ft / t_c / P_obs.
    power_fn(rating, cas_kt, h_press_ft, t_c) -> CNT per engine; when obs carries P_obs (reference tests),
    observed power is used for airborne nodes instead.
    Returns (nodes, info). nodes columns: x_ft, y_ft, z_ft, V_kt, P, bank_deg, kind, ground_roll ('D' or '')."""
    policy = policy or PathPolicy()
    axis_u = np.asarray(axis_u, float) / np.linalg.norm(axis_u)
    air = prepare_track(obs, policy)
    if len(air) < 3:
        raise ValueError("fewer than 3 airborne observations")
    lo = find_liftoff(air, sor_xy, axis_u, tora_ft, policy)
    s_obs = lo["s_obs_ft"]
    # observed airborne points beyond lift-off (along the runway axis while still near the runway)
    beyond = air[(s_obs > lo["s_lo_ft"]) | (air.z_ft > 1500)].copy()
    flags = list(lo["flags"])
    if len(beyond) < 2:
        raise ValueError("no airborne observations beyond the lift-off point")
    gaps = beyond.t_s.diff().fillna(0)
    if (gaps > policy.max_gap_s).any():
        flags.append(f"observation_gap_max_{int(gaps.max())}s")
    th = thin_track(beyond, policy)
    th = th.rename(columns={"gs_kt": "V_kt"})
    th["kind"] = "observed"
    roll = ground_roll_nodes(sor_xy, axis_u, lo["s_lo_ft"], lo["v_lo_kt"])
    lo_node = roll.iloc[-1]
    first = th.iloc[0]
    ic = initial_climb_nodes({"x_ft": lo_node.x_ft, "y_ft": lo_node.y_ft, "V_kt": lo_node.V_kt},
                             {"x_ft": first.x_ft, "y_ft": first.y_ft, "z_ft": first.z_ft, "V_kt": first.V_kt})
    # time stamps for roll / inserted nodes (constant acceleration on the roll; linear in the climb segment)
    t_first = first.t_s
    seg_len = np.hypot(first.x_ft - lo_node.x_ft, first.y_ft - lo_node.y_ft)
    v_mean = max((lo_node.V_kt + first.V_kt) / 2 * KT_TO_FTS, 1.0)
    t_lo = t_first - seg_len / v_mean
    t_roll = 2 * lo["s_lo_ft"] / max(lo_node.V_kt * KT_TO_FTS, 1.0)
    roll["t_s"] = t_lo - t_roll + t_roll * roll.roll_k / roll.roll_n
    if len(ic):
        ic["t_s"] = t_lo + ic.f * (t_first - t_lo)
    # power at the nodes
    def cnt(rating, cas, hp, tc):
        return np.asarray(power_fn(rating, cas, hp, tc), float)
    rating_air = np.where(th.z_ft.to_numpy() < cutback_ft, "MaxTakeoff", "MaxClimb")
    if "P_obs" in th:
        P_air = th.P_obs.to_numpy(float)
    else:
        P_air = np.array([float(cnt(r, c, h, t)) for r, c, h, t in zip(rating_air, th.cas_kt, th.h_press_ft, th.t_c)])
    # ground roll: P_init at V = 0 and P_TO at lift-off (take-off rating, aerodrome pressure altitude), Eq. 3-3e
    h0 = float(th.h_press0.iloc[0]) if "h_press0" in th else 0.0          # aerodrome pressure altitude
    tc0 = float(th.t_c0.iloc[0]) if "t_c0" in th else (float(th.t_c.iloc[0]) if "t_c" in th else 15.0)
    sig0 = float(th.sigma0.iloc[0]) if "sigma0" in th else 1.0
    if "P_roll" in obs.attrs:
        p_init, p_to = obs.attrs["P_roll"]
    else:
        p_init = float(cnt("MaxTakeoff", 0.0, h0, tc0))
        cas_lo = (lo_node.V_kt + float(th.headwind_kt.iloc[0]) if "headwind_kt" in th else lo_node.V_kt) * np.sqrt(sig0)
        p_to = float(cnt("MaxTakeoff", cas_lo, h0, tc0))
    roll["P"] = p_init + roll.roll_k * (p_to - p_init) / roll.roll_n
    if len(ic):
        p1, p2 = max(p_to, 1.0), max(P_air[0], 1.0)
        ic["P"] = np.sqrt(p1 ** 2 + ic.f * (p2 ** 2 - p1 ** 2))           # Eq. 3-2d
    th["P"] = P_air
    th["rating"] = rating_air
    cols = ["t_s", "x_ft", "y_ft", "z_ft", "V_kt", "P", "kind"]
    nodes = pd.concat([roll[cols], ic[cols] if len(ic) else None, th[cols + ["rating"]]], ignore_index=True)
    nodes["rating"] = nodes.rating.fillna("MaxTakeoff")
    nodes["bank_deg"] = bank_angle(nodes, beyond, policy)
    nodes.loc[nodes.kind == "roll", "bank_deg"] = 0.0
    nodes["ground_roll"] = np.where(nodes.kind == "roll", "D", "")
    info = {"s_lo_ft": lo["s_lo_ft"], "v_lo_kt": lo["v_lo_kt"], "n_roll_segments": int(roll.roll_n.iloc[0]),
            "n_inserted_climb_nodes": int(len(ic)), "n_observed_airborne": int(len(beyond)),
            "n_nodes": int(len(nodes)), "p_init": p_init, "p_to": p_to, "flags": flags,
            "max_abs_bank_deg": float(np.abs(nodes.bank_deg).max())}
    return nodes, info


def segments(nodes: pd.DataFrame) -> pd.DataFrame:
    """Consecutive nodes -> segment table (start/end state); the segment after the last roll node is airborne."""
    a, b = nodes.iloc[:-1].reset_index(drop=True), nodes.iloc[1:].reset_index(drop=True)
    seg = pd.DataFrame({"x1": a.x_ft, "y1": a.y_ft, "z1": a.z_ft, "x2": b.x_ft, "y2": b.y_ft, "z2": b.z_ft,
                        "V1": a.V_kt, "V2": b.V_kt, "P1": a.P, "P2": b.P,
                        "bank": (a.bank_deg + b.bank_deg) / 2.0,
                        "ground_roll": np.where((a.kind == "roll") & (b.kind == "roll"), "D", "")})
    lam = np.sqrt((seg.x2 - seg.x1) ** 2 + (seg.y2 - seg.y1) ** 2 + (seg.z2 - seg.z1) ** 2)
    return seg[lam > 1e-6].reset_index(drop=True)
