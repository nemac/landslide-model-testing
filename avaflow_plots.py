"""
Review graphs for each r.avaflow run: the four panels a dam-break study is reported
with, adapted for a slide, so the slide results can be read the same way.

  1  Material in motion against time -- how much ground and water is moving, from
     r.avaflow's own volume table. Growth shows entrainment; a storm run also shows
     the runoff flowing in.
  2  Peak depth down the valley -- how deep the material got, against distance from
     the release point along the path it took.
  3  Arrival time down the valley -- when the material first reached each distance.
     The slope of this line is its speed.
  4  Area by depth band -- how much ground was covered thinly against how much deeply.

Distance is measured along the flow path, traced downhill from the release point
through the ground the material covered, so a bend does not read as distance.

    python3 avaflow_plots.py            every slide and run on disk
    python3 avaflow_plots.py 8          slide 8 only

Writes outputs/plots/<slide>_<run>_review.png, one per run, and
outputs/plots/<slide>_compare.png with every run of that slide on the same axes.
"""
import os, sys, json, glob
import numpy as np, rasterio
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from avaflow_run import load_slides, CELL_M, DEPOSIT_BANDS, DEPOSIT_CUT, OUTPUTS, RUNDIR, INPUTS

PLOTS = os.path.join(OUTPUTS, "plots")
BIN_M = 50.0                                  # distance step for the down-valley panels


def _read(p):
    with rasterio.open(p) as src:
        a = src.read(1).astype("float64"); tr = src.transform; nd = src.nodata
    a[(a == nd) | ~np.isfinite(a)] = np.nan
    return a, tr


def runs_on_disk(s):
    """(run name, folder) for every run of this slide that finished."""
    out = []
    for d in sorted(glob.glob(os.path.join(RUNDIR, s["id"], "*"))):
        name = os.path.basename(d)
        if os.path.exists(os.path.join(d, f"{s['id']}_{name}_hflow_max.tif")):
            out.append((name, d))
    return out


def flow_path(dem, tr, s, covered):
    """
    The path the material took: from the release cell, step to the lowest neighbouring
    cell that the material covered and that has not been visited, until there is none.
    Returns the path's row, col arrays and the distance along it, metres.
    """
    c, r = ~tr * (s["x"], s["y"]); r, c = int(r), int(c)
    ny, nx = dem.shape
    rows, cols, dist = [r], [c], [0.0]
    seen = {(r, c)}
    while True:
        best = None
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                rr, cc = r + dr, c + dc
                if (dr or dc) and 0 <= rr < ny and 0 <= cc < nx and (rr, cc) not in seen and covered[rr, cc]:
                    z = dem[rr, cc]
                    if np.isfinite(z) and (best is None or z < best[0]):
                        best = (z, rr, cc, np.hypot(dr, dc) * CELL_M)
        if best is None:
            break
        _, r, c, step = best
        seen.add((r, c)); rows.append(r); cols.append(c); dist.append(dist[-1] + step)
    return np.array(rows), np.array(cols), np.array(dist)


def down_valley(h, treach, path, tr):
    """Peak depth and first arrival in BIN_M steps of distance along the path."""
    prow, pcol, pdist = path
    wet = np.isfinite(h) & (h > DEPOSIT_CUT)
    rr, cc = np.nonzero(wet)
    if not rr.size:
        return None
    # each covered cell takes the distance of the nearest path cell
    d2 = (rr[:, None] - prow[None, :]) ** 2 + (cc[:, None] - pcol[None, :]) ** 2
    near = d2.argmin(axis=1)
    dist = pdist[near]
    edges = np.arange(0, pdist.max() + BIN_M, BIN_M)
    mid = 0.5 * (edges[:-1] + edges[1:])
    idx = np.clip(np.digitize(dist, edges) - 1, 0, len(mid) - 1)
    peak = np.full(len(mid), np.nan); first = np.full(len(mid), np.nan)
    for i in range(len(mid)):
        m = idx == i
        if m.any():
            peak[i] = np.nanmax(h[rr[m], cc[m]])
            if treach is not None:
                a = treach[rr[m], cc[m]]; a = a[np.isfinite(a) & (a >= 0)]
                if a.size:
                    first[i] = a.min()
    return mid, peak, first


def volumes(run_dir, pf):
    """Time (s) and volume in motion (m3) of ground and water, from r.avaflow's table."""
    p = os.path.join(run_dir, f"{pf}_results", f"{pf}_files", f"{pf}_volumes.txt")
    if not os.path.exists(p):
        return None
    rows = [l.split() for l in open(p).read().strip().splitlines()[1:]]
    t = np.array([float(r[1]) for r in rows]); ground = np.array([float(r[2]) for r in rows])
    water = np.array([float(r[6]) for r in rows]) if len(rows[0]) > 6 else np.zeros_like(t)
    return t, ground, water


def review_figure(s, name, run_dir, path, dem_tr):
    pf = f"ls{s['fid']:02d}"
    h, tr = _read(os.path.join(run_dir, f"{s['id']}_{name}_hflow_max.tif"))
    tp = os.path.join(run_dir, f"{pf}_results", f"{pf}_ascii", f"{pf}_treach.asc")
    treach = _read(tp)[0] if os.path.exists(tp) else None
    prof = down_valley(h, treach, path, tr)
    vol = volumes(run_dir, pf)
    storm = None
    sj = os.path.join(run_dir, "storm.json")
    if os.path.exists(sj):
        storm = json.load(open(sj))

    fig, ax = plt.subplots(2, 2, figsize=(12, 8))
    a = ax[0, 0]
    if vol:
        t, ground, water = vol
        a.plot(t / 60, ground, color="#8b5a2b", lw=2, label="ground in motion")
        if water.max() > 0:
            a.plot(t / 60, water, color="#2b6f8b", lw=2, label="water in motion")
        a.plot(t / 60, ground + water, color="k", lw=1, ls="--", label="total")
        a.axhline(s["volume_m3"], color="grey", lw=0.8, ls=":", label=f"released {s['volume_m3']:,.0f} m³")
        if storm:
            a.plot(t / 60, storm["inflow_m3s"] * t, color="#2b6f8b", lw=1, ls=":",
                   label=f"storm runoff in, {storm['inflow_m3s']} m³/s")
    a.set_xlabel("minutes after release"); a.set_ylabel("m³"); a.set_title("material in motion", fontsize=10)
    a.grid(alpha=0.3); a.legend(fontsize=8, frameon=False)

    a = ax[0, 1]
    if prof:
        mid, peak, _ = prof
        a.plot(mid, peak, color="#8b3a3a", lw=2)
        a.fill_between(mid, 0, np.nan_to_num(peak), color="#8b3a3a", alpha=0.15)
        # the release column itself is metres deep and would flatten everything else
        if len(peak) > 2 and np.isfinite(peak[1:]).any():
            a.set_ylim(0, np.nanmax(peak[1:]) * 1.3)
            a.text(0.98, 0.95, f"release column {np.nanmax(peak):.1f} m deep, off scale", ha="right", va="top",
                   transform=a.transAxes, fontsize=8, color="grey")
    a.set_xlabel("metres down the valley from the release point"); a.set_ylabel("peak depth  m")
    a.set_title("peak depth down the valley", fontsize=10); a.grid(alpha=0.3)

    a = ax[1, 0]
    if prof and np.isfinite(prof[2]).any():
        mid, _, first = prof
        a.plot(mid, first, color="#2b6f8b", lw=2, marker="o", ms=3)
        a.set_ylabel("seconds after release")
    else:
        a.text(0.5, 0.5, "no arrival-time grid for this run", ha="center", va="center", transform=a.transAxes)
    a.set_xlabel("metres down the valley from the release point")
    a.set_title("arrival time down the valley", fontsize=10); a.grid(alpha=0.3)

    a = ax[1, 1]
    labels, areas = [], []
    for lo, hi in DEPOSIT_BANDS:
        m = np.isfinite(h) & (h > lo) & (h <= hi)
        labels.append(f"{lo * 100:g}-{hi * 100:g} cm" if hi < 1e8 else f">{lo * 100:g} cm")
        areas.append(m.sum() * CELL_M * CELL_M)
    a.bar(labels, areas, color="#8b5a2b")
    for i, v in enumerate(areas):
        a.text(i, v, f"{v:,.0f}", ha="center", va="bottom", fontsize=8)
    a.set_ylabel("m²"); a.set_title("ground covered, by how deep the material got", fontsize=10)
    a.grid(alpha=0.3, axis="y")

    fig.suptitle(f"{s['id']}   {name}", fontsize=12)
    fig.tight_layout()
    out = os.path.join(PLOTS, f"{s['id']}_{name}_review.png")
    fig.savefig(out, dpi=130); plt.close(fig)
    return out, prof


def compare_figure(s, profiles):
    """Every run of the slide on the same axes: peak depth and arrival down the valley."""
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.5))
    cmap = plt.get_cmap("viridis"); n = max(len(profiles), 1); top = 0.0
    for i, (name, prof) in enumerate(profiles):
        if not prof:
            continue
        mid, peak, first = prof
        ax[0].plot(mid, peak, color=cmap(i / n), lw=1.8, label=name)
        if len(peak) > 2 and np.isfinite(peak[1:]).any():
            top = max(top, float(np.nanmax(peak[1:])))
        if np.isfinite(first).any():
            ax[1].plot(mid, first, color=cmap(i / n), lw=1.8, label=name)
    if top > 0:
        ax[0].set_ylim(0, top * 1.3)
        ax[0].text(0.98, 0.95, "release column off scale", ha="right", va="top", transform=ax[0].transAxes, fontsize=8, color="grey")
    ax[0].set_xlabel("metres down the valley"); ax[0].set_ylabel("peak depth  m"); ax[0].set_title("peak depth", fontsize=10)
    ax[1].set_xlabel("metres down the valley"); ax[1].set_ylabel("seconds after release"); ax[1].set_title("arrival time", fontsize=10)
    for a in ax:
        a.grid(alpha=0.3); a.legend(fontsize=7, frameon=False)
    fig.suptitle(f"{s['id']}   all runs", fontsize=12); fig.tight_layout()
    out = os.path.join(PLOTS, f"{s['id']}_compare.png")
    fig.savefig(out, dpi=130); plt.close(fig)
    return out


if __name__ == "__main__":
    want = [int(a) for a in sys.argv[1:] if a.isdigit()] or None
    os.makedirs(PLOTS, exist_ok=True)
    slides = load_slides()
    for fid in sorted(slides):
        if want and fid not in want:
            continue
        s = slides[fid]
        runs = runs_on_disk(s)
        if not runs:
            continue
        dem, tr = _read(os.path.join(INPUTS, s["id"], "dem.tif"))
        # the ground any run covered, so every run of the slide shares one path
        covered = np.zeros(dem.shape, bool)
        for name, d in runs:
            h, _ = _read(os.path.join(d, f"{s['id']}_{name}_hflow_max.tif"))
            covered |= np.isfinite(h) & (h > DEPOSIT_CUT)
        path = flow_path(dem, tr, s, covered)
        profiles = []
        for name, d in runs:
            out, prof = review_figure(s, name, d, path, tr)
            profiles.append((name, prof))
            print(f"   {os.path.basename(out)}", flush=True)
        print(f"   {os.path.basename(compare_figure(s, profiles))}", flush=True)
