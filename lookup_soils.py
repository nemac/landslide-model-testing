"""
Look up the soil at each landslide source point and turn it into the two
r.avaflow settings that can be tied to data:

    water share  = how much of the soil's volume is water. Three states are written:
                   saturated (SSURGO "wsatiated_r", or from bulk density when missing),
                   field capacity ("wthirdbar_r") and wilting point ("wfifteenbar_r").
                   The water_share column is the saturated value, which the runs use.
    pile angle   = internal friction angle from the soil's texture (sand/silt/clay),
                   using a standard engineering table by USDA texture class

Soil data come from the USDA Soil Data Access web service (SSURGO). For each
point: the map unit under it, its main soil component, and that soil's layers
down to PROFILE_CM, averaged by layer thickness.

Reads the points from inputs/sourceareas_min_elev.gpkg (not kept in git).
Writes outputs/landslide_soils.csv (one row per slide, fid kept).
"""
import os, csv, json, urllib.request, fiona
from pyproj import Transformer

HERE = os.path.dirname(os.path.abspath(__file__))
OUTPUTS = os.path.join(HERE, "outputs")   # every geopackage and CSV the scripts write
OUT = os.path.join(OUTPUTS, "landslide_soils.csv")
SDA = "https://sdmdataaccess.sc.egov.usda.gov/Tabular/post.rest"
PROFILE_CM = 150                      # depth of soil considered, cm (the slide takes the whole soil)
PARTICLE_DENSITY = 2.65               # g/cm3, for pore space from bulk density when needed

# pile angle (internal friction angle, degrees) by USDA texture class; typical values
# from engineering tables for loose to medium soils
PILE_ANGLE = {
    "sand": 34, "loamy sand": 33, "sandy loam": 31, "loam": 29, "silt loam": 27, "silt": 26,
    "sandy clay loam": 27, "clay loam": 26, "silty clay loam": 25,
    "sandy clay": 24, "silty clay": 22, "clay": 20,
}


def sda(query):
    body = json.dumps({"query": query, "format": "JSON+COLUMNNAME"}).encode()
    req = urllib.request.Request(SDA, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    rows = data.get("Table", [])
    if not rows:
        return []
    cols = rows[0]
    return [dict(zip(cols, r)) for r in rows[1:]]


def texture_class(sand, silt, clay):
    """USDA soil texture triangle, from percent sand, silt, clay."""
    if clay >= 40:
        if sand >= 45: return "sandy clay"
        if silt >= 40: return "silty clay"
        return "clay"
    if clay >= 35 and sand >= 45: return "sandy clay"
    if clay >= 27:
        if sand > 45: return "sandy clay loam"
        if silt >= 40 and clay < 40: return "silty clay loam"
        return "clay loam"
    if clay >= 20 and sand > 45 and silt < 28: return "sandy clay loam"
    if silt >= 80 and clay < 12: return "silt"
    if silt >= 50: return "silt loam"
    if clay >= 7 and sand <= 52 and silt >= 28: return "loam"
    if sand - clay >= 70: return "sand"
    if sand - clay >= 70 - 15 and sand >= 70: return "loamy sand"
    if silt + 1.5 * clay < 15: return "sand"
    if silt + 2 * clay < 30: return "loamy sand"
    return "sandy loam"


def f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def lookup(lon, lat):
    mk = sda(f"SELECT mukey FROM SDA_Get_Mukey_from_intersection_with_WktWgs84('point({lon:.6f} {lat:.6f})')")
    if not mk:
        return None
    mukey = mk[0]["mukey"]
    rows = sda(f"""
        SELECT mu.muname, c.cokey, c.compname, c.comppct_r, c.majcompflag,
               ch.hzname, ch.hzdept_r, ch.hzdepb_r, ch.sandtotal_r, ch.silttotal_r, ch.claytotal_r,
               ch.dbthirdbar_r, ch.wsatiated_r, ch.wthirdbar_r, ch.wfifteenbar_r,
               (SELECT TOP 1 tg.texture FROM chtexturegrp tg WHERE tg.chkey = ch.chkey AND tg.rvindicator = 'Yes') AS texture
        FROM mapunit mu
        JOIN component c ON c.mukey = mu.mukey
        JOIN chorizon ch ON ch.cokey = c.cokey
        WHERE mu.mukey = '{mukey}'
        ORDER BY c.comppct_r DESC, ch.hzdept_r""")
    if not rows:
        return {"mukey": mukey, "muname": sda(f"SELECT muname FROM mapunit WHERE mukey='{mukey}'")[0]["muname"]}
    cokey = rows[0]["cokey"]                          # the main soil in this map unit
    hz = [r for r in rows if r["cokey"] == cokey]
    # thickness-weighted averages over the layers down to PROFILE_CM
    acc = {"sand": [0, 0], "silt": [0, 0], "clay": [0, 0], "wsat": [0, 0], "wfc": [0, 0], "wwp": [0, 0], "bd": [0, 0]}
    for r in hz:
        top, bot = f(r["hzdept_r"]), f(r["hzdepb_r"])
        if top is None or bot is None:
            continue
        bot = min(bot, PROFILE_CM)
        t = bot - top
        if t <= 0:
            continue
        for key, col in (("sand", "sandtotal_r"), ("silt", "silttotal_r"), ("clay", "claytotal_r"),
                         ("wsat", "wsatiated_r"), ("wfc", "wthirdbar_r"), ("wwp", "wfifteenbar_r"),
                         ("bd", "dbthirdbar_r")):
            v = f(r[col])
            if v is not None:
                acc[key][0] += v * t; acc[key][1] += t
    mean = {k: (a / w if w else None) for k, (a, w) in acc.items()}
    # how deep the soil goes before rock: the bottom of the deepest layer the survey
    # describes, cm. Used as how deep a flow can dig (entrainment).
    depths = [f(r["hzdepb_r"]) for r in hz if f(r["hzdepb_r"]) is not None]
    out = {"mukey": mukey, "muname": rows[0]["muname"], "soil": rows[0]["compname"],
           "soil_share_pct": rows[0]["comppct_r"], "surface_texture": hz[0]["texture"],
           "sand_pct": mean["sand"], "silt_pct": mean["silt"], "clay_pct": mean["clay"],
           "soil_depth_cm": max(depths) if depths else None}
    if None not in (mean["sand"], mean["silt"], mean["clay"]):
        out["texture_class"] = texture_class(mean["sand"], mean["silt"], mean["clay"])
        out["pile_angle_deg"] = PILE_ANGLE[out["texture_class"]]
    # water held by the soil, as a share of its volume, at three states:
    #   saturated       every pore full; the most it can hold
    #   field capacity  what is left two days after soaking, once the big pores have drained
    #   wilting point   what plants cannot pull out; the dry-summer floor
    if mean["wsat"] is not None:
        out["water_saturated"] = round(mean["wsat"] / 100, 3); out["water_share_from"] = "saturated water content"
    elif mean["bd"] is not None:
        out["water_saturated"] = round(1 - mean["bd"] / PARTICLE_DENSITY, 3); out["water_share_from"] = "bulk density"
    if mean["wfc"] is not None:
        out["water_field_capacity"] = round(mean["wfc"] / 100, 3)
    if mean["wwp"] is not None:
        out["water_wilting"] = round(mean["wwp"] / 100, 3)
    if "water_saturated" in out:
        out["water_share"] = out["water_saturated"]           # the saturated soil; what the *_soilsat runs use
        if "water_field_capacity" in out:
            # rain (inches) that fills the column from field capacity to saturated
            out["rain_to_saturate_in"] = round((out["water_saturated"] - out["water_field_capacity"]) * PROFILE_CM / 100 / 0.0254, 1)
    return out


if __name__ == "__main__":
    rows = []
    with fiona.open(os.path.join(HERE, "inputs", "sourceareas_min_elev.gpkg")) as l:
        to_ll = Transformer.from_crs(l.crs, "EPSG:4326", always_xy=True)
        for ft in sorted(l, key=lambda ft: int(ft["id"])):
            fid = int(ft["id"])
            lon, lat = to_ll.transform(*ft["geometry"]["coordinates"][:2])
            r = {"source_fid": fid, "slide_id": f"LS-{fid:02d}", "lat": round(lat, 6), "lon": round(lon, 6)}
            try:
                s = lookup(lon, lat) or {}
            except Exception as e:
                s = {"note": f"lookup failed: {e}"}
            r.update(s)
            rows.append(r)
            print(f"{r['slide_id']}  {s.get('soil', '-'):12s} {s.get('texture_class', '-'):16s} "
                  f"pile angle {s.get('pile_angle_deg', '-')}  water share {s.get('water_share', '-')}  "
                  f"({s.get('muname', s.get('note', '-'))})")
    cols = ["source_fid", "slide_id", "lat", "lon", "mukey", "muname", "soil", "soil_share_pct", "surface_texture",
            "sand_pct", "silt_pct", "clay_pct", "texture_class", "pile_angle_deg",
            "water_saturated", "water_field_capacity", "water_wilting", "rain_to_saturate_in",
            "water_share", "water_share_from", "soil_depth_cm", "note"]
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in rows:
            w.writerow({k: (round(v, 1) if isinstance(v, float) and k.endswith("_pct") else v) for k, v in r.items()})
    print(f"wrote {OUT}")
