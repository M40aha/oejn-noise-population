"""Figures and the results summary of a noise run (after `python -m noise.run`).

    PYTHONPATH=src python scripts/noise_figures.py
Writes docs/noise/fig_*.png and docs/noise/results_2026-10-01.md from data/noise/processed + A6 receptors.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from matplotlib.colors import BoundaryNorm, ListedColormap, LogNorm
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "noise" / "processed"
V = ROOT / "data" / "noise" / "validation"
OUT = ROOT / "docs" / "noise"
cfg = yaml.safe_load((ROOT / "config" / "noise.yaml").read_text())
E0, N0 = Transformer.from_crs(4326, 32637, always_xy=True).transform(cfg["aerodrome"]["arp_lon"], cfg["aerodrome"]["arp_lat"])
TO_UTM = Transformer.from_crs(4326, 32637, always_xy=True)
INK, MUTED, GRID = "#1f2328", "#6b7280", "#e5e7eb"
NARROW = {"A320", "A20N", "A321", "A21N", "B738", "B38M", "B737", "B739"}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.titleweight": "bold", "axes.titlesize": 11})


def km(e, n):
    return (np.asarray(e) - E0) / 1000, (np.asarray(n) - N0) / 1000


def grid():
    g = pd.read_parquet(P / "noise_grid.parquet")
    n = int(round(np.sqrt(len(g))))
    x, y = km(g.x_utm37n_m.to_numpy().reshape(n, n), g.y_utm37n_m.to_numpy().reshape(n, n))
    return g, n, x, y


def population_raster(lim=40, cell_km=0.5):
    rec = pd.read_parquet(ROOT / cfg["inputs"]["a6_receptors"], columns=["x_utm37n_m", "y_utm37n_m", "population"])
    x, y = km(rec.x_utm37n_m, rec.y_utm37n_m)
    b = np.arange(-lim, lim + cell_km, cell_km)
    H, _, _ = np.histogram2d(y, x, bins=[b, b], weights=rec.population)
    return b, H / cell_km ** 2


def runways(ax):
    rw = pd.read_csv(ROOT / cfg["inputs"]["runways_csv"])
    for r in rw[rw.runway_end.isin(["34C", "34L", "34R"])].itertuples():
        x1, y1 = km(*TO_UTM.transform(r.threshold_longitude_deg, r.threshold_latitude_deg))
        x2, y2 = km(*TO_UTM.transform(r.opposite_threshold_longitude_deg, r.opposite_threshold_latitude_deg))
        ax.plot([x1, x2], [y1, y2], color=INK, lw=2.2, solid_capstyle="butt", zorder=6)
        ax.annotate(r.runway_end, (x1, y1), xytext=(-14 if r.runway_end == "34L" else 4, -10), textcoords="offset points",
                    fontsize=7.5, color=INK, zorder=7)


def base(ax, lim):
    b, D = population_raster()
    ax.pcolormesh(b, b, np.where(D > 0, D, np.nan), cmap="Greys", norm=LogNorm(50, 30000), alpha=0.55, zorder=1, rasterized=True)
    ax.set_xlim(-lim, lim)
    ax.set_ylim(-lim, lim)
    ax.set_aspect("equal")
    ax.set_xlabel("km east of ARP (UTM 37N)")
    ax.set_ylabel("km north of ARP")
    ax.grid(color=GRID, lw=0.5, zorder=0)
    runways(ax)


def fig_contours(metric, levels, colors, title, fname, label, lim=30):
    g, n, x, y = grid()
    z = g[metric].to_numpy(float).reshape(n, n)
    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    base(ax, lim)
    cmap = ListedColormap(colors)
    norm = BoundaryNorm(levels + [999], cmap.N)
    cf = ax.contourf(x, y, z, levels=levels + [999], cmap=cmap, norm=norm, alpha=0.6, zorder=3)
    ax.contour(x, y, z, levels=levels, colors="white", linewidths=0.6, zorder=4)
    cb = fig.colorbar(cf, ax=ax, shrink=0.75, pad=0.02, ticks=levels)
    cb.set_label(label)
    cb.ax.set_yticklabels([str(v) for v in levels])
    ax.set_title(title, loc="left")
    ax.text(0.0, -0.12, "Observed jet departures, 1 Oct 2026 (A2/Wingbits), ECAC Doc 29 5th Ed., ANP 2.3. Grey: residents per km² "
            "(WorldPop 2026). Departures only.", transform=ax.transAxes, fontsize=7, color=MUTED)
    fig.savefig(OUT / fname, dpi=170, bbox_inches="tight")
    plt.close(fig)


def fig_tracks(lim=40):
    nodes_p = ROOT / "data" / "noise" / "interim" / "flight_path_nodes.parquet"
    if not nodes_p.exists():
        return
    nodes = pd.read_parquet(nodes_p)
    fr = pd.read_csv(P / "flight_results.csv")[["flight_id", "runway"]]
    nodes = nodes.merge(fr, on="flight_id")
    site_e, site_n = E0, N0
    fig, ax = plt.subplots(figsize=(7.2, 7.2))
    base(ax, lim)
    col = {"34C": "#2563eb", "34L": "#d97706"}
    for (fid, rwy), d in nodes.groupby(["flight_id", "runway"]):
        ax.plot(d.x_ft * 0.3048 / 1000, d.y_ft * 0.3048 / 1000, color=col.get(rwy, MUTED), lw=0.5, alpha=0.45, zorder=3)
    for k, c in col.items():
        ax.plot([], [], color=c, lw=2, label=f"{k} ({nodes[nodes.runway == k].flight_id.nunique()} modelled)")
    ax.legend(loc="lower left", frameon=False)
    ax.set_title("Modelled departure flight paths (ground tracks)", loc="left")
    fig.savefig(OUT / "fig_tracks.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def fig_runway(fm):
    t = fm.groupby(["fam", "runway"]).agg(n=("flight_id", "size"), l65=("pop_lamax_ge_65", "mean"), l70=("pop_lamax_ge_70", "mean"))
    fams = [f for f in ("narrowbody", "widebody") if f in t.index.get_level_values(0)]
    fig, axes = plt.subplots(1, 2, figsize=(8.6, 3.4), sharey=False)
    for ax, (col, ttl) in zip(axes, (("l65", "LAmax ≥ 65 dB"), ("l70", "LAmax ≥ 70 dB"))):
        xs = np.arange(len(fams))
        for j, (rw, c) in enumerate((("34C", "#2563eb"), ("34L", "#d97706"))):
            vals = [t.loc[(f, rw), col] / 1000 if (f, rw) in t.index else np.nan for f in fams]
            ns = [int(t.loc[(f, rw), "n"]) if (f, rw) in t.index else 0 for f in fams]
            bars = ax.bar(xs + (j - 0.5) * 0.36, vals, 0.34, color=c, label=rw, zorder=2)
            for b_, v, nn in zip(bars, vals, ns):
                if np.isfinite(v):
                    ax.text(b_.get_x() + b_.get_width() / 2, v, f"{v:.0f}k\nn={nn}", ha="center", va="bottom", fontsize=7, color=INK)
        ax.set_xticks(xs, fams)
        ax.set_title(f"Residents with {ttl}\nper departure (mean)", loc="left", fontsize=10)
        ax.grid(axis="y", color=GRID, zorder=0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.set_ylim(0, np.nanmax(t[col].to_numpy()) / 1000 * 1.3)
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "fig_runway_exposure.png", dpi=170, bbox_inches="tight")
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    fr = pd.read_csv(P / "flight_results.csv")
    fm = fr[fr.path_status == "OK"].copy()
    fm["fam"] = np.where(fm.icao_type.isin(NARROW), "narrowbody", np.where(fm.icao_type.isin(["CL60", "CL61"]), "business jet", "widebody"))
    ex = pd.read_csv(P / "population_exposure.csv")
    man = json.loads((V / "noise_manifest.json").read_text())
    qc = pd.read_csv(V / "noise_qc.csv")
    seq = ["#fde68a", "#fbbf24", "#f59e0b", "#ea580c", "#dc2626", "#991b1b", "#4c0519"]
    fig_contours("Lden", [45, 50, 55, 60, 65, 70, 75], seq, "Lden — departures of 1 Oct 2026", "fig_lden.png", "Lden (dB)")
    fig_contours("Lnight", [40, 45, 50, 55, 60, 65], seq[:6], "Lnight (23–07 local) — departures of 1 Oct 2026", "fig_lnight.png", "Lnight (dB)")
    fig_contours("N70", [1, 5, 10, 20, 50, 100], ["#dbeafe", "#93c5fd", "#60a5fa", "#2563eb", "#1e40af", "#172554"],
                 "N70 — departures with LAmax ≥ 70 dB, 1 Oct 2026", "fig_n70.png", "events")
    fig_tracks()
    fig_runway(fm)

    def pop(metric, band):
        r = ex[(ex.metric == metric) & (ex.band == band)]
        return f"{r.population.iloc[0]:,.0f}" if len(r) else "–"
    st = man["status_counts"]
    fam_tab = fm.groupby(["runway", "fam"]).agg(n=("flight_id", "size"), l60=("pop_lamax_ge_60", "mean"), l65=("pop_lamax_ge_65", "mean"),
                                               l70=("pop_lamax_ge_70", "mean"), s80=("pop_sel_ge_80", "mean")).reset_index()
    typ = fm.groupby("icao_type").agg(n=("flight_id", "size"), anp=("anp_acft_id", "first"), d=("delta_applied_db", "first"),
                                      m=("mapping_method", "first"), l70=("pop_lamax_ge_70", "mean")).sort_values("n", ascending=False)
    L = []
    L.append("# Noise results — observed OEJN departures, 1 October 2026\n")
    L.append(f"Release `{cfg['release_id']}` · run {man['created_utc']} · runtime {man['runtime_s']:.0f} s · method: "
             "[methodology_noise.md](methodology_noise.md)\n")
    L.append("> **Departures only, one day.** No arrivals, ground noise or other days. Full take-off thrust assumed. "
             "The values describe this day's departure noise; they are not annual or regulatory contours.\n")
    L.append("## Coverage\n")
    L.append("| A2 events | accepted departures (in scope) | modelled | no aircraft type (A3) | type not mappable (helicopter / piston / CL61) | path failed |")
    L.append("|---|---|---|---|---|---|")
    L.append(f"| {man['flights_total']} | {man['flights_in_scope']} | **{man['flights_modelled']}** | {st.get('NO_TYPE', 0)} | "
             f"{st.get('UNMAPPED', 0)} | {st.get('PATH_FAILED', 0)} |\n")
    L.append(f"Modelled by runway: 34C {int((fm.runway == '34C').sum())}, 34L {int((fm.runway == '34L').sum())}. "
             f"{st.get('PROXY_ZERO_DELTA', 0)} departures (B78X, A339) use an ANP proxy with Δ = 0 dB (certified levels pending). "
             f"Local periods: day {int((fm.period == 'day').sum())}, evening {int((fm.period == 'evening').sum())}, night {int((fm.period == 'night').sum())}.\n")
    L.append("## Residents exposed (A6 WorldPop 2026, 3.8 M people inside the 80 × 80 km grid)\n")
    L.append("| Indicator | ≥ 45 | ≥ 50 | ≥ 55 | ≥ 60 | ≥ 65 | ≥ 70 | ≥ 75 |\n|---|---|---|---|---|---|---|---|")
    L.append("| Lden (dB) | " + " | ".join(pop("Lden", f">={v} (cumulative)") for v in (45, 50, 55, 60, 65, 70, 75)) + " |")
    L.append("| Lnight (dB) | " + " | ".join(pop("Lnight", f">={v} (cumulative)") for v in (45, 50, 55, 60, 65)) + " | – | – |\n")
    L.append("| Number-above (events in the day) | ≥ 1 | ≥ 5 | ≥ 10 | ≥ 20 | ≥ 50 | ≥ 100 |\n|---|---|---|---|---|---|---|")
    for k in ("N60", "N65", "N70"):
        L.append(f"| {k} | " + " | ".join(pop(k, f">={v} events") for v in (1, 5, 10, 20, 50, 100)) + " |")
    L.append("")
    L.append(f"WHO 2018 exposure–response (indicative only; designed for long-term exposure to all operations): "
             f"{pop('WHO2018_highly_annoyed_indicative', 'Lden 40-75 dB')} highly annoyed, "
             f"{pop('WHO2018_highly_sleep_disturbed_indicative', 'Lnight 40-65 dB')} highly sleep-disturbed.\n")
    L.append("## Per departure, by runway and aircraft class (mean residents)\n")
    L.append("| Runway | Class | Departures | LAmax ≥ 60 | LAmax ≥ 65 | LAmax ≥ 70 | SEL ≥ 80 |\n|---|---|---|---|---|---|---|")
    for r in fam_tab.itertuples():
        L.append(f"| {r.runway} | {r.fam} | {r.n} | {r.l60:,.0f} | {r.l65:,.0f} | {r.l70:,.0f} | {r.s80:,.0f} |")
    L.append("\nCompare runways within a class: the fleet mix differs (widebodies use 34C almost exclusively). "
             "34L has few departures this day (n small), so the comparison is indicative.\n")
    tt = fm.groupby(["icao_type", "runway"]).agg(n=("flight_id", "size"), l65=("pop_lamax_ge_65", "median"),
                                                 l70=("pop_lamax_ge_70", "median")).reset_index()
    both = [t_ for t_, g_ in tt.groupby("icao_type") if set(g_.runway) >= {"34C", "34L"} and g_.n.min() >= 2]
    L.append("**Same aircraft type on both runways** (median residents per departure; types with ≥ 2 departures on each runway):\n")
    L.append("| Type | 34C n | 34C LAmax ≥ 65 | 34C LAmax ≥ 70 | 34L n | 34L LAmax ≥ 65 | 34L LAmax ≥ 70 |\n|---|---|---|---|---|---|---|")
    for t_ in both:
        a, b = tt[(tt.icao_type == t_) & (tt.runway == "34C")].iloc[0], tt[(tt.icao_type == t_) & (tt.runway == "34L")].iloc[0]
        L.append(f"| {t_} | {a.n} | {a.l65:,.0f} | {a.l70:,.0f} | {b.n} | {b.l65:,.0f} | {b.l70:,.0f} |")
    L.append("\nWithin a type the two runways expose similar numbers of residents per departure; the class-level gap above "
             "comes mostly from the fleet mix (more A320ceo / B737 on 34L, more A320neo on 34C). The aircraft type matters more "
             "than the runway on this day: e.g. A320 vs A20N medians differ several-fold. That type effect rests on the A5 substitution "
             "(engines unknown for most airframes: A320 -> ANP A320-211 +0.2 dB, A20N -> A320-232 -3.5 dB, Doc 29 conservative variant), "
             "so it should be confirmed once engine types are resolved.\n")
    L.append("Runway contribution to the day's Lden (each runway's departures alone):\n")
    L.append("| Runway | Lden ≥ 45 | ≥ 55 | ≥ 65 |\n|---|---|---|---|")
    for k in ("34C", "34L"):
        L.append(f"| {k} | " + " | ".join(pop(f"Lden_{k}_alone", f">={v}") for v in (45, 55, 65)) + " |")
    L.append("\n## Aircraft types modelled\n")
    L.append("| ICAO type | Departures | ANP proxy | Δ (dB) | Mapping | mean residents LAmax ≥ 70 |\n|---|---|---|---|---|---|")
    for t_, r in typ.iterrows():
        L.append(f"| {t_} | {r.n} | {r.anp} | {r.d:+.1f} | {r.m} | {r.l70:,.0f} |")
    L.append("\n## QC\n")
    L.append("| Check | Status | Detail |\n|---|---|---|")
    for r in qc.itertuples():
        L.append(f"| {r.check} | {r.status} | {str(r.detail).replace('|', '/')} |")
    L.append("\n## Figures\n")
    for f_, cap in (("fig_lden.png", "Lden contours"), ("fig_lnight.png", "Lnight contours"), ("fig_n70.png", "N70"),
                    ("fig_tracks.png", "Modelled ground tracks"), ("fig_runway_exposure.png", "Residents per departure by runway")):
        if (OUT / f_).exists():
            L.append(f"![{cap}]({f_})\n")
    (OUT / "results_2026-10-01.md").write_text("\n".join(L))
    print("written", OUT / "results_2026-10-01.md")


if __name__ == "__main__":
    main()
