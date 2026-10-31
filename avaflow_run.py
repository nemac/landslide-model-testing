"""
Run r.avaflow (4.0G, in GRASS GIS 8.4) on the landslide sources.

    python3 avaflow_run.py                 all 20 slides
    python3 avaflow_run.py 8 13            slides with these fids only
    python3 avaflow_run.py --collect       rebuild the geopackages from runs already on disk
    python3 avaflow_run.py 8 --runs stopslope15_soilsat_entrain
                                           only these runs (names from RUNS) for slide 8
    python3 avaflow_run.py --workers 4     slides in parallel, 4 at a time (default WORKERS)
    python3 avaflow_run.py --redo          rerun runs that are already on disk (otherwise kept)

Reads the source areas from inputs/sourceareas_dambreach.gpkg and the release
points from inputs/sourceareas_min_elev.gpkg (neither is kept in git).

For each slide (fid):
  1. inputs/LS-<fid>/dem.tif        10 m terrain from the USGS 3DEP 1/3 arc-second
                                    DEM, 1.5 km each side of the point, NC state
                                    plane metres (EPSG:6542)
     inputs/LS-<fid>/hrelease.tif   release thickness over the source polygon:
                                    the table volume / polygon area (RELEASE_THICKNESS)
  2. a GRASS mapset LS-<fid> in grassdata/landslides, the two rasters imported
  3. r.avaflow.40G -e -k, one-phase model, run in avaflow_runs/LS-<fid>/
     (r.avaflow writes LS<fid>_results/ there)
  4. avaflow_runs/LS-<fid>/LS-<fid>_hflow_max.tif   deepest flow, metres
     avaflow_runs/LS-<fid>/LS-<fid>_vflow_max.tif   fastest flow, m/s

Then every slide's deepest-flow raster goes into one geopackage per slide,
outputs/landslide_<fid>_avaflow.gpkg (layer avaflow_<run name>, depth-band polygons
with source_fid, slide_id, run, stop_slope_deg, pile_angle_deg,
depth_band_m, max_depth_m, area_m2), and outputs/landslide_avaflow_summary.csv.
Everything the scripts write (geopackages and CSVs) goes in outputs/, which is
not kept in git.

Settings are the block below. Each entry in RUNS is one r.avaflow run per
slide; add entries to sweep the friction.
"""
import os, sys, csv, json, math, subprocess, shutil
import numpy as np, rasterio, fiona
from rasterio import features
from rasterio.transform import from_origin
from rasterio.warp import transform_bounds, reproject, Resampling
from shapely.geometry import shape, mapping, MultiPolygon
from shapely.ops import transform as stransform, unary_union
from pyproj import Transformer

# ---- settings ---------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUTS = os.path.join(HERE, "outputs")   # every geopackage and CSV the scripts write
GRASS = "/usr/local/bin/grass"
CRS = "EPSG:6542"                   # NAD83(2011) / North Carolina, metres
CELL_M = 10.0
HALF_BOX_M = 2500.0                 # terrain 2.5 km each side of the point (was 1.5 km; low stop slopes clipped)
DEM_URL = "/vsicurl/https://prd-tnm.s3.amazonaws.com/StagedProducts/Elevation/13/TIFF/USGS_Seamless_DEM_13.vrt"
RELEASE_THICKNESS = "volume"        # "volume": table volume / polygon area; "height": the table's height column
RELEASE_AT = "point"                # "point": the whole volume on the cell at the point, the lowest spot of the
                                    #          source, so the flow starts below the "lake"; "polygon": spread over it
FT = 0.304800609601219
AF = 1233.48
MAP_DEPTH = 0.05                    # below this the flow is not drawn
MIN_FLOW_M = 0.01                   # r.avaflow's own lower limit for a flow height to count
BANDS = [(0.05, 0.5), (0.5, 1.0), (1.0, 2.0), (2.0, 1e9)]
# one-phase runs: name, internal friction angle (deg), stop slope (deg: the ground
# slope the material needs to keep moving; on flatter ground it stops),
# fluid/turbulent friction, density (kg/m3), output interval and end time (s)
# Every run has three settings. One name each, everywhere:
#   stop_slope   ground slope (deg) below which the material drags and stops.
#                r.avaflow calls it the basal friction angle. Set by hand in every run.
#   pile_angle   steepest slope (deg) a loose pile of the material stands at.
#                r.avaflow calls it the internal friction angle. Must not be below
#                the stop slope. 35 by hand, or from the soil's texture ("soil": True).
#   water_share  share of the released volume that is water (0.25 = a quarter). The
#                ground part keeps the stop slope and pile angle; the water part has
#                no friction of its own. 0 = dry. Set by hand, or from the soil
#                ("soil": True gives the saturated soil).
# Run names say the settings: stopslope<deg>_<water>. _dry = no water; _water25 = 25 %
# water by hand; _pile20 = pile angle 20 by hand; _soilsat = pile angle and saturated
# water share from the soil.
# density is the solid grains, 2650 kg/m3, as r.avaflow asks; the model handles the pore
# space between grains itself. Runs before 29 Oct 2026 used 2000 (loose bulk soil).
D = {"fluid": 0.0, "density": 2650, "time": "10,600"}   # fluid friction, kg/m3, output step and end (s)
# The run matrix. Every run: pile angle and saturated water share from the soil under
# the release point (outputs/landslide_soils.csv, made by lookup_soils.py), full volume,
# entrainment on (the flow digs up the ground it runs over and grows; how deep comes
# from the soil survey's soil depth, how easily from ENTRAIN_LOG10 below).
# Crossed: the stop slope at four levels, and the storm (none, or runoff from a 24 hour
# rainfall of that many inches flowing in at the release point, see storm_inflow).
STOP_SLOPES = (5, 10, 15, 20, 25, 30)
STORMS_IN = (None, 5, 10)
# how much lets go: None = the volume in the source table (its acre-feet column, which
# works out to 0.071 m over each polygon: the 2.5 ft it was meant to be, with square
# metres mistaken for square feet when converting to acres); or polygon area x this
# depth in metres. The run name carries _depth<cm>cm for the latter.
RELEASE_DEPTHS_M = (None, 0.03, 0.05, 0.09)
RUNS = [
    {"name": f"stopslope{ss}_soilsat_entrain" + (f"_storm{st}in" if st else "") + (f"_depth{round(dp * 100)}cm" if dp else ""),
     "soil": True, "stop_slope": ss, "entrain": True, **({"storm_in": st} if st else {}), **({"depth_m": dp} if dp else {}), **D}
    for dp in RELEASE_DEPTHS_M for ss in STOP_SLOPES for st in STORMS_IN
]


def release_volume(s, run):
    """The volume released in this run, m3: polygon area x depth when the run sets one, else the table's."""
    return s["area_m2"] * run["depth_m"] if run.get("depth_m") else s["volume_m3"]
WATER_DENSITY = 1000
SOILS_CSV = os.path.join(OUTPUTS, "landslide_soils.csv")
# entrainment coefficient, as a power of ten: -7 is effectively off, -6 ten times more
# digging than -7. Published r.avaflow debris-flow work sits around -6.5 to -6. Not
# measurable; checked by how much the flow grows (mapped Blue Ridge flows: 3 to 10 fold).
ENTRAIN_LOG10 = -6.5
# storm runoff fed in at the release point, as simply as possible:
#   catchment  = the cells that drain to the point, from the DEM (GRASS r.watershed)
#   rain rate  = the storm's peak hour. In a 24 hour design storm about 45 % of the
#                rain falls in the peak hour (SCS type II, used for inland NC). The
#                slide is assumed to happen then.
#   runoff     = all of that rain runs off, since the soil is already saturated
#   inflow     = rain rate x catchment, m3/s, steady for the whole run
# The inflow is added to the release cell every time step. r.avaflow 4.0G is built
# to read the hydrograph's height column as a flow rate in m3/s in this mode
# (main.c: HYDADD = 2, "impose on centre"), so that column carries the inflow and
# the speed column is 0: the water arrives with no push of its own and gravity
# takes it from there.
STORM_PEAK_SHARE = 0.45
INCH = 0.0254


def storm_inflow(s, rain_in, catchment_cells):
    """Steady inflow of storm runoff at the release point, m3/s, and the numbers behind it."""
    area = catchment_cells * CELL_M * CELL_M
    rate = rain_in * INCH * STORM_PEAK_SHARE / 3600          # m of rain per second in the peak hour
    q = rate * area
    return {"storm_in": rain_in, "catchment_m2": round(area), "peak_rain_in_per_h": round(rain_in * STORM_PEAK_SHARE, 2),
            "inflow_m3s": round(q, 3), "x": round(s["x"], 1), "y": round(s["y"], 1)}


def soil_row(s):
    """This slide's row of the soils table."""
    with open(SOILS_CSV) as f:
        for r in csv.DictReader(f):
            if int(r["source_fid"]) == s["fid"] and r.get("pile_angle_deg") and r.get("water_share"):
                return r
    raise RuntimeError(f"no soil values for {s['id']} in {os.path.basename(SOILS_CSV)}; run lookup_soils.py")


def soil_name(r):
    return f"{r['soil']} {r['texture_class']} (SSURGO {r['mukey']}: {r['muname']})"


def run_settings(run, s):
    """The run's settings with the soil values filled in for this slide where asked."""
    run = dict(run)
    run["settings_from"] = "set by hand"
    if run.get("soil"):
        r = soil_row(s)
        run["pile_angle"] = float(r["pile_angle_deg"])
        run["water_share"] = float(r["water_share"])
        run["settings_from"] = f"pile angle and saturated water share from soil: {soil_name(r)}"
        if run.get("entrain"):
            if not r.get("soil_depth_cm"):
                raise RuntimeError(f"no soil depth for {s['id']}; rerun lookup_soils.py")
            run["erodible_depth_m"] = float(r["soil_depth_cm"]) / 100
            run["settings_from"] += f"; entrainment on, can dig {run['erodible_depth_m']:.2f} m (soil depth), coefficient 10^{ENTRAIN_LOG10:g}"
    if run.get("storm_in"):
        run["settings_from"] += f"; storm runoff from a {run['storm_in']:g} in / 24 h storm fed in at the point (see storm.json in the run folder)"
    if run.get("depth_m"):
        run["settings_from"] += f"; released volume = source area x {run['depth_m']:g} m"
    return run
# -----------------------------------------------------------------------------

GRASSDATA = os.path.join(HERE, "grassdata")
PROJECT = os.path.join(GRASSDATA, "landslides")
INPUTS = os.path.join(HERE, "inputs")
RUNDIR = os.path.join(HERE, "avaflow_runs")


def grass_exec(mapset, *cmd, cwd=None):
    """Run one GRASS command in the given mapset of the landslides project."""
    full = [GRASS, os.path.join(PROJECT, mapset), "--exec"] + [str(c) for c in cmd]
    r = subprocess.run(full, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:1])} failed:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
    return r.stdout


def load_slides():
    pts = {}
    with fiona.open(os.path.join(INPUTS, "sourceareas_min_elev.gpkg")) as l:
        to = Transformer.from_crs(l.crs, CRS, always_xy=True)
        for ft in l:
            x, y = ft["geometry"]["coordinates"][:2]
            pts[int(ft["id"])] = to.transform(x, y)
    out = {}
    with fiona.open(os.path.join(INPUTS, "sourceareas_dambreach.gpkg")) as l:
        to = Transformer.from_crs(l.crs, CRS, always_xy=True)
        for ft in l:
            fid = int(ft["id"])
            if fid not in pts:
                continue
            poly = stransform(to.transform, shape(ft["geometry"]))
            p = ft["properties"]
            vol = float(p["acrefeet"]) * AF
            out[fid] = {"fid": fid, "id": f"LS-{fid:02d}", "x": pts[fid][0], "y": pts[fid][1],
                        "poly": poly, "area_m2": poly.area, "volume_m3": vol,
                        "height_m": float(p["height"]) * FT}
    return out


def _trim_results(wd, pf):
    """
    Drop what r.avaflow wrote that nothing here reads: the grid for every output step
    (hflow0000, basechange0001, ...), the hillshade and temperature grids, and the plot
    and 3D export folders. A run shrinks from about 250 MB to about 15 MB. Kept: the
    _max and _fin grids, treach, the front grids, and the _files text tables.
    """
    import re
    res = os.path.join(wd, f"{pf}_results")
    asc = os.path.join(res, f"{pf}_ascii")
    if os.path.isdir(asc):
        step = re.compile(rf"^{pf}_(hflow|basechange|hillshade|temperature|vflow|pflow|tflow|tsun)\d*\.asc$")
        for fn in os.listdir(asc):
            if step.match(fn) and not fn.endswith(("_max.asc", "_fin.asc")) and not re.match(rf"^{pf}_(hflow|basechange|vflow|pflow|tflow)[123]?_(max|fin)\.asc$", fn):
                try:
                    os.remove(os.path.join(asc, fn))
                except OSError:
                    pass
    for sub in (f"{pf}_plots", f"{pf}_vr", f"{pf}_aimec"):
        shutil.rmtree(os.path.join(res, sub), ignore_errors=True)


def _grid_ok(tif, nx):
    """Does this grid match the current box (nx cells each way)?"""
    try:
        with rasterio.open(tif) as a:
            return a.width == nx and a.height == nx
    except Exception:
        return False


def make_inputs(s, depth_m=None):
    """The DEM (cut once) and the release raster for this volume (one file per release depth)."""
    d = os.path.join(INPUTS, s["id"]); os.makedirs(d, exist_ok=True)
    dem_p = os.path.join(d, "dem.tif")
    rel_p = os.path.join(d, f"hrelease_depth{round(depth_m * 100)}cm.tif" if depth_m else "hrelease.tif")
    left = math.floor((s["x"] - HALF_BOX_M) / CELL_M) * CELL_M
    bottom = math.floor((s["y"] - HALF_BOX_M) / CELL_M) * CELL_M
    right, top = left + 2 * HALF_BOX_M, bottom + 2 * HALF_BOX_M
    nx = ny = int(round(2 * HALF_BOX_M / CELL_M))
    tr = from_origin(left, top, CELL_M, CELL_M)
    if os.path.exists(dem_p) and not _grid_ok(dem_p, nx):
        os.remove(dem_p)                      # cut for a different box size; cut again
    if not os.path.exists(dem_p):
        with rasterio.open(DEM_URL) as src:
            sb = transform_bounds(CRS, src.crs, left, bottom, right, top, densify_pts=41)
            pad = 0.05 * max(sb[2] - sb[0], sb[3] - sb[1])
            win = rasterio.windows.from_bounds(sb[0] - pad, sb[1] - pad, sb[2] + pad, sb[3] + pad,
                                               transform=src.transform).round_offsets().round_lengths()
            block = src.read(1, window=win, masked=True).astype(np.float32)
            block = np.where(block.mask, np.nan, block.data).astype(np.float32)
            dem = np.full((ny, nx), np.nan, np.float32)
            reproject(source=block, destination=dem, src_transform=src.window_transform(win), src_crs=src.crs,
                      src_nodata=np.nan, dst_transform=tr, dst_crs=CRS, dst_nodata=np.nan,
                      resampling=Resampling.bilinear)
        with rasterio.open(dem_p, "w", driver="GTiff", height=ny, width=nx, count=1, dtype="float32",
                           crs=CRS, transform=tr, nodata=-9999.0) as dst:
            dst.write(np.where(np.isfinite(dem), dem, -9999.0).astype(np.float32), 1)
    if depth_m:
        vol = s["area_m2"] * depth_m
    else:
        vol = s["volume_m3"] if RELEASE_THICKNESS == "volume" else s["height_m"] * s["area_m2"]
    if RELEASE_AT == "point":
        rel = np.zeros((ny, nx), np.float32)
        c, r = ~tr * (s["x"], s["y"])
        rel[int(r), int(c)] = vol / (CELL_M * CELL_M)
        thick = float(rel.max())
    else:
        thick = vol / s["area_m2"]
        rel = features.rasterize([(mapping(s["poly"]), thick)], out_shape=(ny, nx), transform=tr,
                                 fill=0.0, all_touched=False, dtype="float32")
        if not (rel > 0).any():      # a source smaller than a cell: put it on the point's cell
            c, r = ~tr * (s["x"], s["y"]); rel[int(r), int(c)] = vol / (CELL_M * CELL_M)
    with rasterio.open(rel_p, "w", driver="GTiff", height=ny, width=nx, count=1, dtype="float32",
                       crs=CRS, transform=tr, nodata=-9999.0) as dst:
        dst.write(rel, 1)
    return dem_p, rel_p, thick, float((rel > 0).sum() * CELL_M * CELL_M), (top, bottom, left, right)


def run_slide(s, runs=RUNS, redo=False):
    dem_p, rel_p, thick, rel_area, (top, bottom, left, right) = make_inputs(s)
    nx = int(round(2 * HALF_BOX_M / CELL_M))
    print(f"{s['id']} (fid {s['fid']}): {s['volume_m3']:,.0f} m³ in the table, released {'at the point' if RELEASE_AT == 'point' else 'over the source'}, "
          f"{rel_area:,.0f} m², {thick:.2f} m thick", flush=True)
    ms = os.path.join(PROJECT, s["id"])
    if not os.path.isdir(ms):
        subprocess.run([GRASS, "-c", "-e", ms], check=True, capture_output=True)
    grass_exec(s["id"], "r.in.gdal", "--overwrite", "--quiet", f"input={dem_p}", "output=dem")
    grass_exec(s["id"], "r.in.gdal", "--overwrite", "--quiet", f"input={rel_p}", "output=hrelease")
    grass_exec(s["id"], "g.region", "raster=dem")
    out = []
    loaded_rel = rel_p
    for run in runs:
        run = run_settings(run, s)
        wd = os.path.join(RUNDIR, s["id"], run["name"]); os.makedirs(wd, exist_ok=True)
        pf = f"ls{s['fid']:02d}"
        # the release raster for this run's volume, swapped into GRASS only when it changes
        _, run_rel_p, _, _, _ = make_inputs(s, run.get("depth_m"))
        if run_rel_p != loaded_rel:
            grass_exec(s["id"], "r.in.gdal", "--overwrite", "--quiet", f"input={run_rel_p}", "output=hrelease")
            grass_exec(s["id"], "g.region", "raster=dem")
            loaded_rel = run_rel_p
        # already on disk for this box size: keep it (--redo forces a rerun)
        done_h = os.path.join(wd, f"{s['id']}_{run['name']}_hflow_max.tif")
        done_d = os.path.join(wd, f"{s['id']}_{run['name']}_deposit.tif")
        if not redo and os.path.exists(done_h) and os.path.exists(done_d) and _grid_ok(done_h, nx):
            print(f"   {run['name']}: already run, kept", flush=True)
            out.append((run, done_h, done_d))
            continue
        shutil.rmtree(os.path.join(wd, f"{pf}_results"), ignore_errors=True)
        water = float(run.get("water_share", 0.0))
        if water > 0:
            # ground-and-water run: r.avaflow's three-material model with the middle
            # material left empty. The release map is split: (1 - water) ground, water water.
            # friction list = pile angle x3, stop slope x3, extra x3 (ground, middle, water)
            mix = ["phases=3", f"rhrelease1={1 - water:g}",
                   f"density={run['density']},1850,{WATER_DENSITY}",
                   f"friction={run['pile_angle']},{run['pile_angle']},0,{run['stop_slope']},{run['stop_slope']},0,0,0,0"]
        else:
            mix = ["phases=1", f"density={run['density']}",
                   f"friction={run['pile_angle']},{run['stop_slope']},{run['fluid']}"]
        if run.get("entrain"):
            # a raster of how deep the flow may dig in each cell: the soil depth from the
            # survey, the same everywhere in the box. Written next to the DEM and imported.
            with rasterio.open(dem_p) as dsrc:
                prof = dsrc.profile; dem_arr = dsrc.read(1)
            ero = np.where(dem_arr == dsrc.nodata, 0.0, run["erodible_depth_m"]).astype(np.float32)
            ero_p = os.path.join(os.path.dirname(dem_p), "erodible_depth.tif")
            with rasterio.open(ero_p, "w", **prof) as d:
                d.write(ero, 1)
            grass_exec(s["id"], "r.in.gdal", "--overwrite", "--quiet", f"input={ero_p}", "output=erodible_depth")
            grass_exec(s["id"], "g.region", "raster=dem")
            mix += ["centrainment=1", f"entrainment={ENTRAIN_LOG10:g},0.0", "hentrmax=erodible_depth"]
            if water > 0:
                mix.append(f"rhentrmax1={1 - water:g}")     # the dug-up soil is the same wet soil as the release
        if run.get("storm_in"):
            # storm runoff at the point: how many cells drain to it, then a steady inflow
            grass_exec(s["id"], "r.watershed", "-s", "--overwrite", "--quiet", "elevation=dem", "accumulation=acc")
            cells = abs(float(grass_exec(s["id"], "r.what", "map=acc", f"coordinates={s['x']},{s['y']}").strip().split("|")[-1]))
            storm = storm_inflow(s, run["storm_in"], cells)
            end_s = int(run["time"].split(",")[1]); step_s = int(run["time"].split(",")[0])
            hyd_p = os.path.join(wd, "storm_hydrograph.txt")
            with open(hyd_p, "w") as f:                      # header, then time, and per material: rate (m3/s), speed
                f.write("T Q1 V1 Q2 V2 Q3 V3\n")             # water is material 3; materials 1 and 2 get nothing
                for t in range(0, end_s + step_s, step_s):
                    f.write(f"{t} 0 0 0 0 {storm['inflow_m3s']:g} 0\n")
            with open(os.path.join(wd, "storm.json"), "w") as f:
                json.dump(storm, f, indent=1)
            # hydrocoords: x, y, profile length, angle. Only the point matters in this mode.
            mix += [f"hydrograph={hyd_p}", f"hydrocoords={s['x']:.1f},{s['y']:.1f},{CELL_M:g},0"]
            print(f"   storm: {storm['catchment_m2']:,} m² drains to the point; {storm['inflow_m3s']} m³/s of runoff for {end_s} s "
                  f"= {storm['inflow_m3s'] * end_s:,.0f} m³ of water", flush=True)
        grass_exec(s["id"], "r.avaflow.40G", "-e", "-k", f"prefix={pf}", "elevation=dem", "hrelease=hrelease",
                   *mix, f"time={run['time']}", f"cellsize={CELL_M:g}",
                   f"thresholds={MIN_FLOW_M},10000,10000,{MIN_FLOW_M},0.000001",
                   # r.avaflow starts from the project's default region, so the box must be given
                   f"aoicoords={top:.0f},{bottom:.0f},{left:.0f},{right:.0f}", cwd=wd)
        # r.avaflow resets the GRASS region to one cell when it finishes, so the
        # results are taken from the ascii grids it writes, not exported from GRASS
        asc = os.path.join(wd, f"{pf}_results", f"{pf}_ascii")
        htif = os.path.join(wd, f"{s['id']}_{run['name']}_hflow_max.tif")
        vtif = os.path.join(wd, f"{s['id']}_{run['name']}_vflow_max.tif")
        dtif = os.path.join(wd, f"{s['id']}_{run['name']}_deposit.tif")
        btif = os.path.join(wd, f"{s['id']}_{run['name']}_basechange.tif")   # ground dug out (-) or laid down (+), m
        for src_name, dst in ((f"{pf}_hflow_max.asc", htif), (f"{pf}_vflow_max.asc", vtif), (f"{pf}_hflow_fin.asc", dtif),
                              (f"{pf}_basechange_fin.asc", btif)):
            p = os.path.join(asc, src_name)
            if not os.path.exists(p):
                continue
            with rasterio.open(p) as a:
                arr = a.read(1).astype(np.float32); atr = a.transform
            with rasterio.open(dst, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                               dtype="float32", crs=CRS, transform=atr, nodata=-9999.0) as d:
                d.write(arr, 1)
        _trim_results(wd, pf)
        out.append((run, htif, dtif))
        print(f"   {run['name']}: stop slope {run['stop_slope']}°, pile angle {run['pile_angle']}°, water share {water:.0%} -> {os.path.basename(htif)}", flush=True)
    return out


DEPOSIT_CUT = 0.01                  # ground counts as covered when the material got deeper than this
DEPOSIT_BANDS = [(0.01, 0.05), (0.05, 0.2), (0.2, 0.5), (0.5, 1.0), (1.0, 1e9)]


def _bands_to_layer(gp, layer, h, tr, crs, bands, props, thick_name):
    """Write one layer of depth-band polygons for grid h."""
    schema = {"geometry": "MultiPolygon",
              "properties": {"source_fid": "int", "slide_id": "str", "run": "str", "stop_slope_deg": "float",
                             "pile_angle_deg": "float", "water_share": "float", "settings_from": "str",
                             "band_m": "str", thick_name: "float",
                             "area_m2": "float", "volume_m3": "float"}}
    feats = []
    for lo, hi in bands:
        band = (h > lo) & (h <= hi)
        if not band.any():
            continue
        geoms = [shape(g) for g, v in features.shapes(band.astype(np.uint8), mask=band, transform=tr) if v == 1]
        u = unary_union(geoms)
        if u.geom_type == "Polygon":
            u = MultiPolygon([u])
        feats.append({"geometry": mapping(u),
                      "properties": dict(props, band_m=f"{lo:g}-{hi:g}" if hi < 1e8 else f">{lo:g}",
                                         **{thick_name: round(float(h[band].max()), 3)},
                                         area_m2=round(float(band.sum()) * CELL_M * CELL_M, 1),
                                         volume_m3=round(float(h[band].sum()) * CELL_M * CELL_M, 1))})
    with fiona.open(gp, "w", driver="GPKG", layer=layer, schema=schema, crs=crs) as dst:
        for ft in feats:
            dst.write(ft)


ARRIVAL_BIN_MIN = 5          # arrival-time polygons: minutes after release, in bins this wide


def _arrival_layer(gp, layer, treach_s, tr, crs, props):
    """
    One polygon per ARRIVAL_BIN_MIN-minute bin of when the material first reached each
    cell, from r.avaflow's treach grid (seconds; cells never reached hold a huge value).
    """
    reached = np.isfinite(treach_s) & (treach_s >= 0) & (treach_s < 1e5)
    if not reached.any():
        return
    minutes = np.where(reached, treach_s / 60.0, np.nan)
    schema = {"geometry": "MultiPolygon",
              "properties": dict({k: ("int" if isinstance(v, int) else "float" if isinstance(v, float) else "str") for k, v in props.items()},
                                 arrival_min="str", first_min="float", area_m2="float")}
    feats = []
    top = int(np.ceil(np.nanmax(minutes) / ARRIVAL_BIN_MIN)) * ARRIVAL_BIN_MIN
    for lo in range(0, max(top, ARRIVAL_BIN_MIN), ARRIVAL_BIN_MIN):
        hi = lo + ARRIVAL_BIN_MIN
        band = reached & (minutes >= lo) & (minutes < hi)
        if not band.any():
            continue
        geoms = [shape(g) for g, v in features.shapes(band.astype(np.uint8), mask=band, transform=tr) if v == 1]
        u = unary_union(geoms)
        if u.geom_type == "Polygon":
            u = MultiPolygon([u])
        feats.append({"geometry": mapping(u),
                      "properties": dict(props, arrival_min=f"{lo}-{hi}", first_min=round(float(np.nanmin(minutes[band])), 2),
                                         area_m2=round(float(band.sum()) * CELL_M * CELL_M, 1))})
    with fiona.open(gp, "w", driver="GPKG", layer=layer, schema=schema, crs=crs) as dst:
        for ft in feats:
            dst.write(ft)


def _drop_layer(gp, layer):
    """Remove one layer from a geopackage if it is there; the file and its other layers stay."""
    if not os.path.exists(gp):
        return
    try:
        layers = fiona.listlayers(gp)
    except Exception:
        # a half-written file (two writers at once, or a crash mid-write): it is unreadable
        # and holds nothing recoverable, so start the file again from the runs on disk
        print(f"   {os.path.basename(gp)} unreadable, rebuilding it", flush=True)
        os.remove(gp)
        return
    if layer in layers:
        fiona.remove(gp, driver="GPKG", layer=layer)


def _read(tif):
    with rasterio.open(tif) as src:
        h = src.read(1); tr = src.transform; crs = src.crs
        h = np.where((h == src.nodata) | ~np.isfinite(h), 0.0, h)
    return h, tr, crs


def _farthest(h, tr, s, cut):
    wet = h > cut
    if not wet.any():
        return 0.0
    rr, cc = np.nonzero(wet); xs, ys = rasterio.transform.xy(tr, rr, cc)
    return float(np.max(np.hypot(np.array(xs) - s["x"], np.array(ys) - s["y"])))


def collect(s, results, summary):
    """
    One geopackage per slide, one layer per run:
      deposit_<run>  all the ground the material covered from the point down to where it
                     stopped, banded by how deep it got; starts at the point
    """
    gp = os.path.join(OUTPUTS, f"landslide_{s['fid']:02d}_avaflow.gpkg")
    # the geopackage is kept; each run's layers are replaced as they come, nothing else is touched
    for run, htif, dtif in results:
        for lyr in (f"deposit_{run['name']}", f"arrival_{run['name']}", f"hydrograph_{run['name']}"):
            _drop_layer(gp, lyr)
        run = run_settings(run, s)
        props = {"source_fid": s["fid"], "slide_id": s["id"], "run": run["name"],
                 "stop_slope_deg": float(run["stop_slope"]), "pile_angle_deg": float(run["pile_angle"]),
                 "water_share": float(run.get("water_share", 0.0)), "settings_from": run["settings_from"]}
        # the deposit: all the ground the material covered from the point down to
        # where it stopped, banded by the deepest it got in each cell
        h, tr, crs = _read(htif)
        _bands_to_layer(gp, f"deposit_{run['name']}", h, tr, crs, DEPOSIT_BANDS, props, "max_depth_m")
        # when the material first arrived, in 5 minute bins
        pf = f"ls{s['fid']:02d}"
        treach_p = os.path.join(os.path.dirname(htif), f"{pf}_results", f"{pf}_ascii", f"{pf}_treach.asc")
        if os.path.exists(treach_p):
            with rasterio.open(treach_p) as a:
                _arrival_layer(gp, f"arrival_{run['name']}", a.read(1).astype("float64"), a.transform, crs, props)
        d, _, _ = _read(dtif)
        # the storm inflow point, if this run had one: where the runoff came in and how much
        storm = {}
        sj = os.path.join(os.path.dirname(htif), "storm.json")
        if os.path.exists(sj):
            with open(sj) as f:
                storm = json.load(f)
            end_s = int(run["time"].split(",")[1])
            sprops = dict(props, storm_in=float(storm["storm_in"]), catchment_m2=float(storm["catchment_m2"]),
                          peak_rain_in_per_h=float(storm["peak_rain_in_per_h"]), inflow_m3s=float(storm["inflow_m3s"]),
                          inflow_total_m3=round(storm["inflow_m3s"] * end_s, 1))
            schema = {"geometry": "Point", "properties": {k: ("str" if isinstance(v, str) else "int" if isinstance(v, int) else "float")
                                                          for k, v in sprops.items()}}
            with fiona.open(gp, "w", driver="GPKG", layer=f"hydrograph_{run['name']}", schema=schema, crs=crs) as dst:
                dst.write({"geometry": {"type": "Point", "coordinates": (storm["x"], storm["y"])}, "properties": sprops})
        # how much ground the flow dug up, from the basechange grid (negative = dug out)
        btif = os.path.join(os.path.dirname(htif), f"{s['id']}_{run['name']}_basechange.tif")
        entrained = 0.0
        if os.path.exists(btif):
            b, _, _ = _read(btif)
            entrained = float(-np.minimum(b, 0.0).sum()) * CELL_M * CELL_M
        summary.append({"source_fid": s["fid"], "slide_id": s["id"], "run": run["name"],
                        "stop_slope_deg": run["stop_slope"], "pile_angle_deg": run["pile_angle"],
                        "water_share": float(run.get("water_share", 0.0)), "settings_from": run["settings_from"],
                        "deposit_area_m2": round(float((h > DEPOSIT_CUT).sum()) * CELL_M * CELL_M, 1),
                        "deposit_max_depth_m": round(float(h.max()), 3),
                        "deposit_farthest_m": round(_farthest(h, tr, s, DEPOSIT_CUT), 1),
                        "resting_thickest_m": round(float(d.max()), 3),
                        "released_m3": round(release_volume(s, run), 1),
                        "entrained_m3": round(entrained, 1),
                        "growth": round((release_volume(s, run) + entrained) / release_volume(s, run), 2),
                        "release_depth_m": run.get("depth_m", round(s["volume_m3"] / s["area_m2"], 3)),
                        "storm_in": storm.get("storm_in", 0),
                        "storm_water_m3": round(storm["inflow_m3s"] * int(run["time"].split(",")[1]), 1) if storm else 0})
    print(f"   -> {os.path.basename(gp)}", flush=True)


def existing_results(s):
    """The runs already on disk for this slide, for --collect."""
    out = []
    for run in RUNS:
        wd = os.path.join(RUNDIR, s["id"], run["name"])
        htif = os.path.join(wd, f"{s['id']}_{run['name']}_hflow_max.tif")
        dtif = os.path.join(wd, f"{s['id']}_{run['name']}_deposit.tif")
        pf = f"ls{s['fid']:02d}"
        asc = os.path.join(wd, f"{pf}_results", f"{pf}_ascii")
        if not os.path.exists(dtif) and os.path.exists(os.path.join(asc, f"{pf}_hflow_fin.asc")):
            with rasterio.open(os.path.join(asc, f"{pf}_hflow_fin.asc")) as a:
                arr = a.read(1).astype(np.float32); atr = a.transform
            with rasterio.open(dtif, "w", driver="GTiff", height=arr.shape[0], width=arr.shape[1], count=1,
                               dtype="float32", crs=CRS, transform=atr, nodata=-9999.0) as dd:
                dd.write(arr, 1)
        if os.path.exists(htif) and os.path.exists(dtif):
            out.append((run, htif, dtif))
    return out


# slides run in parallel, one slide per worker (every run of that slide, in order).
# Each slide has its own GRASS mapset and run folders, so workers do not collide.
# r.avaflow uses one core per run; this Mac has 10 cores, so 6 leaves room for the rest.
WORKERS = 6


def _run_one(args):
    """One slide, all its runs; for the worker pool. Returns (slide id, error or None)."""
    s, runs, redo = args
    try:
        run_slide(s, runs, redo)
        return s["id"], None
    except Exception as e:
        return s["id"], str(e)


if __name__ == "__main__":
    argv = sys.argv[1:]
    collect_only = "--collect" in argv
    redo = "--redo" in argv                  # rerun even if the result is already on disk
    runs, workers = RUNS, WORKERS
    if "--runs" in argv:                     # only these run names, e.g. --runs stopslope15_soilsat_entrain
        i = argv.index("--runs"); names = argv[i + 1].split(","); del argv[i:i + 2]
        runs = [r for r in RUNS if r["name"] in names]
        if len(runs) != len(names):
            sys.exit(f"unknown run name(s): {set(names) - {r['name'] for r in runs}}")
    if "--workers" in argv:
        i = argv.index("--workers"); workers = max(1, int(argv[i + 1])); del argv[i:i + 2]
    want = [int(a) for a in argv if a.isdigit()] or None
    os.makedirs(GRASSDATA, exist_ok=True); os.makedirs(RUNDIR, exist_ok=True); os.makedirs(OUTPUTS, exist_ok=True)
    if not os.path.isdir(PROJECT):
        subprocess.run([GRASS, "-c", CRS, "-e", PROJECT], check=True, capture_output=True)
    slides = load_slides()
    summary = []
    if not collect_only:
        todo = [slides[fid] for fid in sorted(slides) if not want or fid in want]
        if workers > 1 and len(todo) > 1:
            from multiprocessing import Pool
            print(f"{len(todo)} slides, {len(runs)} runs each, {workers} at a time", flush=True)
            with Pool(min(workers, len(todo))) as pool:
                for sid, err in pool.imap_unordered(_run_one, [(s, runs, redo) for s in todo]):
                    print(f"{sid} {'done' if err is None else 'failed: ' + err}", flush=True)
        else:
            for s in todo:
                sid, err = _run_one((s, runs, redo))
                if err:
                    print(f"   {sid} failed: {err}", flush=True)
    # the geopackages and the summary always cover every run on disk, for every slide
    for fid in sorted(slides):
        results = existing_results(slides[fid])
        if results:
            collect(slides[fid], results, summary)
    # the summary is kept too: rows for the slides and runs just collected replace the old
    # ones; rows for anything else stay as they were
    sp = os.path.join(OUTPUTS, "landslide_avaflow_summary.csv")
    cols = ["source_fid", "slide_id", "run", "stop_slope_deg", "pile_angle_deg", "water_share", "settings_from",
            "deposit_area_m2", "deposit_max_depth_m", "deposit_farthest_m",
            "resting_thickest_m", "released_m3", "entrained_m3", "growth", "release_depth_m", "storm_in", "storm_water_m3"]
    fresh = {(r["slide_id"], r["run"]) for r in summary}
    old = []
    if os.path.exists(sp):
        old = [r for r in csv.DictReader(open(sp)) if (r["slide_id"], r["run"]) not in fresh]
    rows = sorted(old + [{k: str(v) for k, v in r.items()} for r in summary], key=lambda r: (int(r["source_fid"]), r["run"]))
    with open(sp, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader(); w.writerows([{c: r.get(c, "") for c in cols} for r in rows])
    print(f"summary: {len(summary)} rows -> {os.path.basename(sp)}")
