"""
Build the data the web viewer reads, from the geopackages in outputs/ and the source
geopackages in inputs/. Rerun after any model run.

    python3 make_viewer_data.py

Writes
  viewer/public/data/landslides.pmtiles   one tile set, five layers:
        deposit     every run's deposit polygons (banded by peak depth)
        arrival     every run's arrival-time polygons (5 minute bins)
        hydrograph  the storm inflow points
        sources     the source polygons
        points      the release points
      The viewer filters deposit / arrival / hydrograph by the run name, so there is
      one file for every run and every slide.
  viewer/public/data/index.json           slides, run names, and the summary table

Needs tippecanoe on the path (brew install tippecanoe).
"""
import os, sys, csv, json, glob, shutil, subprocess, tempfile
import fiona
from shapely.geometry import shape, mapping
from shapely.ops import transform as stransform
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from avaflow_run import RUNS, STOP_SLOPES, STORMS_IN, RELEASE_DEPTHS_M   # only the runs the project currently makes
ACTIVE_RUNS = {r["name"] for r in RUNS}
OUTPUTS = os.path.join(HERE, "outputs")
INPUTS = os.path.join(HERE, "inputs")
VIEWER_DATA = os.path.join(HERE, "viewer", "public", "data")
# attributes kept in the tiles, per layer kind. Everything else is dropped to keep tiles small.
KEEP = {
    "deposit": ["source_fid", "slide_id", "run", "stop_slope_deg", "pile_angle_deg", "water_share", "band_m", "max_depth_m", "area_m2", "volume_m3"],
    "arrival": ["source_fid", "slide_id", "run", "arrival_min", "first_min", "area_m2"],
    "hydrograph": ["source_fid", "slide_id", "run", "storm_in", "catchment_m2", "peak_rain_in_per_h", "inflow_m3s", "inflow_total_m3"],
}


def to_wgs84(crs):
    return Transformer.from_crs(crs, "EPSG:4326", always_xy=True).transform


def features_from(gpkg, layer, keep):
    with fiona.open(gpkg, layer=layer) as src:
        tf = to_wgs84(src.crs)
        for ft in src:
            geom = stransform(tf, shape(ft["geometry"]))
            props = {k: ft["properties"][k] for k in keep if k in ft["properties"]}
            yield {"type": "Feature", "geometry": mapping(geom), "properties": props}


def write_geojson(path, feats):
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": list(feats)}, f)


# NC Geological Survey landslide inventory (ArcGIS feature service), drawn under the model
# results for context. 32,000-odd polygons, so it is fetched once, cached in outputs/, and
# tiled into its own small file; it only changes when --refresh-inventory is given.
INVENTORY_URL = "https://services2.arcgis.com/kCu40SDxsCGcuUWO/ArcGIS/rest/services/NC_Landslide_Inventory/FeatureServer/2"
INVENTORY_FIELDS = "FeatureType,LandslideType,AssociatedStorm,ExistenceConfidence"
INVENTORY_CACHE = os.path.join(OUTPUTS, "nc_landslide_inventory.geojson")
INVENTORY_TILES = os.path.join(VIEWER_DATA, "nc_landslide_inventory.pmtiles")


def build_inventory(refresh=False):
    import urllib.request, urllib.parse
    if refresh or not os.path.exists(INVENTORY_CACHE):
        feats, offset, page = [], 0, 2000
        while True:
            q = urllib.parse.urlencode({"where": "1=1", "outFields": INVENTORY_FIELDS, "outSR": 4326, "f": "geojson",
                                        "resultOffset": offset, "resultRecordCount": page})
            with urllib.request.urlopen(f"{INVENTORY_URL}/query?{q}", timeout=120) as r:
                got = json.loads(r.read().decode()).get("features", [])
            feats.extend(got)
            print(f"inventory: {len(feats)} features fetched", flush=True)
            if len(got) < page:
                break
            offset += page
        with open(INVENTORY_CACHE, "w") as f:
            json.dump({"type": "FeatureCollection", "features": feats}, f)
    if refresh or not os.path.exists(INVENTORY_TILES):
        subprocess.run(["tippecanoe", "-o", INVENTORY_TILES, "--force", "-l", "inventory", "-Z6", "-z14",
                        "--coalesce-densest-as-needed", "--extend-zooms-if-still-dropping", "--quiet", INVENTORY_CACHE], check=True)
        print(f"wrote {os.path.relpath(INVENTORY_TILES, HERE)} ({os.path.getsize(INVENTORY_TILES) / 1e6:.1f} MB)")


def main():
    if shutil.which("tippecanoe") is None:
        sys.exit("tippecanoe not found; brew install tippecanoe")
    os.makedirs(VIEWER_DATA, exist_ok=True)
    build_inventory(refresh="--refresh-inventory" in sys.argv)
    tmp = tempfile.mkdtemp(prefix="viewer_build_")

    # model results, every slide and run, into three GeoJSON files
    collected = {"deposit": [], "arrival": [], "hydrograph": []}
    runs = set()
    for gp in sorted(glob.glob(os.path.join(OUTPUTS, "landslide_*_avaflow.gpkg"))):
        for layer in fiona.listlayers(gp):
            kind, _, run = layer.partition("_")
            if kind in collected and run in ACTIVE_RUNS:
                runs.add(run)
                collected[kind].extend(features_from(gp, layer, KEEP[kind]))
    for kind, feats in collected.items():
        write_geojson(os.path.join(tmp, f"{kind}.geojson"), feats)
        print(f"{kind}: {len(feats)} features")

    # the sources and release points
    slides = []
    with fiona.open(os.path.join(INPUTS, "sourceareas_min_elev.gpkg")) as src:
        tf = to_wgs84(src.crs); pts = []
        for ft in src:
            fid = int(ft["id"]); g = stransform(tf, shape(ft["geometry"]))
            pts.append({"type": "Feature", "geometry": mapping(g), "properties": {"source_fid": fid, "slide_id": f"LS-{fid:02d}"}})
            slides.append({"fid": fid, "id": f"LS-{fid:02d}", "lon": round(g.x, 6), "lat": round(g.y, 6)})
    write_geojson(os.path.join(tmp, "points.geojson"), pts)
    with fiona.open(os.path.join(INPUTS, "sourceareas_dambreach.gpkg")) as src:
        tf = to_wgs84(src.crs); polys = []
        for ft in src:
            fid = int(ft["id"]); p = ft["properties"]
            polys.append({"type": "Feature", "geometry": mapping(stransform(tf, shape(ft["geometry"]))),
                          "properties": {"source_fid": fid, "slide_id": f"LS-{fid:02d}", "acrefeet": p.get("acrefeet"), "height_ft": p.get("height")}})
    write_geojson(os.path.join(tmp, "sources.geojson"), polys)

    # one pmtiles, five layers
    out = os.path.join(VIEWER_DATA, "landslides.pmtiles")
    cmd = ["tippecanoe", "-o", out, "--force", "-Z8", "-z15", "--extend-zooms-if-still-dropping", "--no-tile-size-limit",
           "--no-feature-limit", "--quiet"]
    for kind in ("deposit", "arrival", "hydrograph", "sources", "points"):
        cmd += ["-L", f"{kind}:{os.path.join(tmp, kind + '.geojson')}"]
    subprocess.run(cmd, check=True)
    print(f"wrote {os.path.relpath(out, HERE)} ({os.path.getsize(out) / 1e6:.1f} MB)")

    # the index the viewer reads: slides, runs, summary rows, soils
    summary = []
    sp = os.path.join(OUTPUTS, "landslide_avaflow_summary.csv")
    if os.path.exists(sp):
        summary = [r for r in csv.DictReader(open(sp)) if r["run"] in ACTIVE_RUNS]
    soils = {}
    so = os.path.join(OUTPUTS, "landslide_soils.csv")
    if os.path.exists(so):
        for r in csv.DictReader(open(so)):
            soils[r["slide_id"]] = {k: r[k] for k in ("soil", "texture_class", "pile_angle_deg", "water_share", "soil_depth_cm") if k in r}
    for s in slides:
        s["soil"] = soils.get(s["id"], {})
    with open(os.path.join(VIEWER_DATA, "index.json"), "w") as f:
        # runs in the order they are listed in avaflow_run.py
        import time
        json.dump({"built": int(time.time()), "slides": slides, "runs": [r["name"] for r in RUNS if r["name"] in runs],
                   "stop_slopes": list(STOP_SLOPES), "storms_in": [s for s in STORMS_IN if s],
                   "depths_m": [d for d in RELEASE_DEPTHS_M if d],
                   "summary": summary}, f)
    print(f"index.json: {len(slides)} slides, {len(runs)} runs, {len(summary)} summary rows")

    # the chart data for the viewer's own charts (the PNG figures stay in outputs/plots only)
    cj = os.path.join(OUTPUTS, "plots", "charts.json")
    if os.path.exists(cj):
        shutil.copy(cj, os.path.join(VIEWER_DATA, "charts.json")); print("copied charts.json")
    shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
