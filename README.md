# landslide-model-testing

Maps the ground a landslide covers once it lets go, for a set of source areas in
western North Carolina, using the open-source flow model r.avaflow (version 4.0G)
inside GRASS GIS 8.4. Everything is driven by two python scripts in this folder.
This is screening-level work: the aim is a reasonable footprint for each slide, not
an engineering design.

## Files

| file | what it is |
|---|---|
| `inputs/sourceareas_dambreach.gpkg` | the slide source areas (polygons). `acrefeet` = volume of material, `height` (ft). The `fid` is the slide id. Not kept in git; copy it in. |
| `inputs/sourceareas_min_elev.gpkg` | one point per source: its lowest spot, where the material is released. Same `fid`. Not kept in git; copy it in. |
| `avaflow_run.py` | builds the inputs, runs r.avaflow, and writes the geopackages and summary |
| `lookup_soils.py` | looks up the USDA soil (SSURGO) under each point and turns it into two model settings |
| `install_avaflow.sh` | installs r.avaflow into GRASS 8.4 on macOS (see Setup) |
| `docs/r_avaflow_inputs.md` | every r.avaflow input, explained for a GIS user with no geology background |
| `docs/slide8_storm_test_plan.md` | proposed next test on slide 8: rain to water share formula, renaming, run list. Not yet run |

Made by the scripts (not kept in git). Every geopackage and CSV the scripts write
goes in `outputs/`:

| file | what it is |
|---|---|
| `outputs/landslide_soils.csv` | result of the soil lookup, one row per slide |
| `outputs/landslide_<fid>_avaflow.gpkg` | one per slide, one layer per run (see Outputs) |
| `outputs/landslide_avaflow_summary.csv` | one row per slide and run |
| `outputs/review.qgz` | QGIS project for looking at the results (hand-made, not written by the scripts) |
| `inputs/LS-<fid>/` | the 10 m terrain (`dem.tif`) and release map (`hrelease.tif`) for that slide |
| `avaflow_runs/LS-<fid>/<run>/` | r.avaflow's own results plus the depth grids as GeoTIFFs |
| `grassdata/landslides/` | the GRASS project, one mapset per slide |
| `logs/` | run logs |

## Setup

1. GRASS GIS 8.4 for macOS, installed as `/Applications/GRASS-8.4.app`. Everything
   here runs GRASS from the command line in the background; the GRASS window is
   never opened.
2. `bash install_avaflow.sh` downloads, compiles and installs r.avaflow. It is a
   hand build because the normal `g.extension` install fails on macOS. The script
   says why in its header.
3. A python with `numpy rasterio fiona shapely pyproj` for the two scripts here.
4. The two source geopackages, `sourceareas_dambreach.gpkg` and
   `sourceareas_min_elev.gpkg`, copied into `inputs/`. Neither is kept in git.

## Running

```
python3 lookup_soils.py                 # once: soil settings for every slide -> outputs/landslide_soils.csv
python3 avaflow_run.py                  # every run in RUNS for all 20 slides (slow)
python3 avaflow_run.py 8                # all runs for slide 8 only
python3 avaflow_run.py 8 --runs stopslope15_soilsat,stopslope15_rain7in_k3   # named runs for slide 8
python3 avaflow_run.py --collect        # rebuild the geopackages and summary from runs on disk
```

Each r.avaflow run takes about two minutes. After any run the geopackages and the
summary are rebuilt for every slide from whatever runs are on disk, so they always
show everything that has been run.

What a run does, for one slide:

1. cuts a 3 km square of 10 m terrain around the point from the USGS 1/3 arc-second
   elevation data (NC state plane, EPSG:6542);
2. puts the whole volume on the one 10 m cell at the point, as a tall column, so the
   material starts at the lowest spot of the source and runs from there;
3. runs r.avaflow for 10 model minutes;
4. keeps the deepest the material got in every cell, and how thick it lies at rest.

## All settings on one page

These are the only things we set. Everything else in r.avaflow is at its default.

| what | value we use | where it comes from |
|---|---|---|
| terrain | 10 m DEM, a 3 km square around the slide | USGS, downloaded once per slide |
| where it starts | the lowest point of the source polygon, one 10 m cell | the source geopackages in `inputs/` |
| how much | acre-feet from the source table, converted to m³, all on that one cell | the source table |
| how long | 10 model minutes, a result written every 10 s | fixed |
| stop slope | 8, 10, 12, 15, 18, 20 or 25 degrees | set by hand, one per run |
| pile angle | 35 by hand, or from the soil: sandy loam 31, loam 29 | soil survey texture, via a standard table |
| water share | one of four ways, below | share of the moving mass that is water |
| density | soil grains 2650 kg/m³, water 1000 | fixed. Runs before 29 Oct 2026 used 2000 |

The four ways a run gets its water share. The run name says which:

| run name ends in | water share | how |
|---|---|---|
| `_dry`, `_pile20` and so on | 0 | no water |
| `_water25`, `_water50`, `_water75` | 0.25, 0.50, 0.75 | set by hand |
| `_soilsat` | slide 8: 0.19 | the soil survey's saturated water content, soil completely full |
| `_rain5in_k1` and so on | computed | the storm formula, below |

The storm formula, for a storm of R inches in 24 hours:

| step | formula | slide 8, 7 inch storm |
|---|---|---|
| water in the soil | the smaller of: saturated, or field capacity + R / 1.5 m | 0.19 (full) |
| rain left over | R minus the rain to saturate (4.3 in for slide 8), or 0 | 2.7 in |
| water share for the run | water in soil + k × (rain left over / 1.5 m) | k=1: 0.24, k=3: 0.33 |

k is the one assumed number: the stream water the slide collects on its way down
the hollow, as a multiple of the leftover rain depth over its own footprint. 0 none,
1 once, 3 three times. Runs use 1 and 3 to see whether it matters.

What every run reports: ground covered in m² (cells where the material got deeper
than 1 cm), farthest reach in metres from the start point, and the deepest it got.

## Settings, in plain words

All settings are at the top of `avaflow_run.py`. The list `RUNS` holds one entry per
run; each slide is run once per entry.

**Stop slope** (r.avaflow calls it the basal friction angle). How much grip there is
between the bottom of the slide and the ground, written as the ground slope at which
the two balance. Steeper than that, the material keeps moving; flatter than that,
it drags and stops. 20 is stiff, dry, rocky material that stops on a hillside. 10 is
soupy material that runs on down to gentle ground. Nothing measures this directly;
it is set by matching the model to past slides whose deposits were mapped. This is
the setting that matters most.

**Water share.** How much of the released volume is water (0.25 = a quarter). The
dry runs have none. With water, r.avaflow runs its two-material model: the ground
part keeps the stop slope and pile angle, the water part has no grip of its own and
flows like water, dragging the ground along. More water means it runs much farther
and thins out. The soil lookup sets this to how much water the soil holds when
soaked (its pore space), which is a fair guess for slides that let go in a storm.

**Pile angle** (r.avaflow: internal friction angle). The steepest slope a loose pile
of the material can stand at on its own. Dry gravel holds a steep cone; wet soil
slumps flat. The soil lookup sets it from the soil's texture. In the slide 8 tests
it made no difference at all, because the hollow the slide runs in holds it in.

The run names say the settings: `stopslope<deg>_<water>`. Anything not named is at
the standard value, pile angle 35, no water:

| run name | stop slope | pile angle | water share |
|---|---|---|---|
| `stopslope20_dry`, `stopslope15_dry`, `stopslope10_dry` | 20 / 15 / 10 | 35 | none |
| `stopslope15_water0` ... `stopslope15_water75` | 15 | 35 | 0, 25, 50, 75 % by hand |
| `stopslope15_pile15` ... `stopslope15_pile40` | 15 | 15 ... 40 | none |
| `stopslope25_soilsat` ... `stopslope8_soilsat` | 25 / 20 / 18 / 15 / 12 / 10 / 8 | from the soil | saturated soil |
| `stopslope15_rain0in` ... `stopslope15_rain4in` | 15 | from the soil | soil after that much rain |
| `stopslope<deg>_rain<N>in_k<K>` | 25 ... 8 | from the soil | saturated soil plus channel water, pickup K |

## How rain becomes water share

r.avaflow has no rain input, so a storm total has to be turned into a water share.
The soil survey gives three water contents for each soil, averaged over the top 1.5 m:
**saturated** (every pore full), **field capacity** (two days after soaking, once the
big pores drain; the normal wet-season state) and **wilting point** (the dry-summer
floor). `lookup_soils.py` writes all three. The formula is a one-column bucket, filled
from the top, starting at field capacity:

```
water in soil after the storm   theta  = min( saturated , field_capacity + rain / 1.5 m )
rain that saturates the column  P_sat  = ( saturated - field_capacity ) x 1.5 m
rain left over, runs off        excess = max( 0 , rain - P_sat )
water share used in the model   theta + pickup x excess / 1.5 m
```

`pickup` is how many times the leftover rain depth, over the slide's own footprint,
the flow collects from the hollow on its way down. It is an assumption, not a
measurement; runs use 1 and 3 to see whether it matters. For slide 8 (saturated 19 %,
field capacity 12 %) the column saturates at 4.3 inches, close to the NCGS trigger
threshold of about 5 inches in 24 hours. Every `_soilsat` run is therefore the
"4.3 inches or more" storm; below that the soil is drier, above it only channel water
adds more. Full reasoning and what the formula leaves out:
`docs/slide8_storm_test_plan.md`.

Other things fixed in the script: 10 m cells, a 3 km box, density 2650 kg/m³ for the
ground material, 10 model minutes, ground counts as covered when the material got
deeper than 1 cm (`DEPOSIT_CUT`).

## Outputs

Each slide's geopackage has one layer per run, named `deposit_<run>`. The layer is
all the ground the material covered from the point to where it stopped, in bands by
how deep it got (1 to 5 cm, 5 to 20 cm, 20 to 50 cm, 50 cm to 1 m, over 1 m). Every
feature carries the settings so a layer can always be traced:

`source_fid`, `slide_id`, `run`, `stop_slope_deg`, `internal_friction_deg` (the pile
angle), `water_share`, `settings_from` ("set by hand", or the soil the values came
from with its SSURGO map unit), `band_m`, `max_depth_m`, `area_m2`, `volume_m3`.

The summary has one row per slide and run with the same settings plus
`deposit_area_m2`, `deposit_max_depth_m`, `deposit_farthest_m` (how far from the
point it reached) and `resting_thickest_m`.

## What the tests on slide 8 showed (October 2026)

Slide 8 (fid 8) sits on the Toecane bouldery sandy loam. All 20 slides have the three
dry runs; the rest were run on slide 8 only.

| run | ground covered m² | farthest m | widest m |
|---|---|---|---|
| slope20 (dry) | 30,100 | 233 | 156 |
| slope15 (dry) | 44,300 | 400 | 180 |
| slope10 (dry) | 60,000 | 603 | 152 |
| slope15, quarter water | 111,900 | 1,030 | 256 |
| slope15, half water | 165,700 | 1,475 | 266 |
| slope15, three-quarter water | 300,800 | 1,565 | 472 |
| slope15, pile angle 15 to 40 | 44,000 to 44,600 | 400 | 180 |
| slope20, soil (pile 31, water 0.19) | 76,200 | 718 | 180 |
| slope15, soil | 105,900 | 1,001 | 246 |
| slope10, soil | 185,900 | 1,489 | 303 |

Stop slope sweep with the soil settings (pile angle 31, water 19 %), 29 October 2026.
The four new levels bracket what slides do in western North Carolina: 25 is stiff dry
rocky soil that stops on the hillside, 18 a slide that reaches the hollow, 12 a
typical channelized debris flow, 8 a very mobile saturated flow with long runout.

| stop slope | ground covered m² | farthest m |
|---|---|---|
| 25 | 54,700 | 504 |
| 20 | 76,200 | 718 |
| 18 | 84,900 | 850 |
| 15 | 105,900 | 1,001 |
| 12 | 152,400 | 1,358 |
| 10 | 185,900 | 1,490 |
| 8 | 246,800 | 1,552 |

Area roughly doubles between 18 and 10, and again from 12 to 8. The 10 and 8 runs
reach the edge of the 3 km box, so their real runout is longer than shown.

### Storm test, 29 October 2026

Water share from the storm formula (see "All settings on one page"), stop slope 15,
pile angle 31 from the soil. Slide 8's soil saturates at 4.3 inches.

| run | storm | k | water share | ground covered m² | farthest m |
|---|---|---|---|---|---|
| `stopslope15_dry` | none, no water | | 0 | 44,300 | 400 |
| `stopslope15_rain0in` | none, wet-season soil | | 0.12 | 98,600 | 969 |
| `stopslope15_rain2in` | 2 in | | 0.15 | 102,400 | 986 |
| `stopslope15_rain3in` | 3 in | | 0.17 | 104,600 | 991 |
| `stopslope15_rain4in` | 4 in | | 0.19 | 107,100 | 1,001 |
| `stopslope15_soilsat` | 4.3 in and up, soil full | | 0.19 | 105,900 | 1,001 |
| `stopslope15_rain5in_k1` | 5 in | 1 | 0.20 | 108,100 | 1,008 |
| `stopslope15_rain7in_k1` | 7 in | 1 | 0.24 | 110,600 | 1,020 |
| `stopslope15_rain10in_k1` | 10 in | 1 | 0.29 | 116,400 | 1,076 |
| `stopslope15_rain5in_k3` | 5 in | 3 | 0.23 | 110,300 | 1,020 |
| `stopslope15_rain7in_k3` | 7 in | 3 | 0.33 | 122,700 | 1,130 |
| `stopslope15_rain10in_k3` | 10 in | 3 | 0.48 | 160,400 | 1,455 |

The same 7 inch, k=3 storm at the other stop slopes, beside the saturated soil run:

| stop slope | soil full (0.19) m² | 7 in, k=3 (0.33) m² | change |
|---|---|---|---|
| 25 | 54,700 | 55,200 | +1 % |
| 18 | 84,900 | 96,400 | +14 % |
| 15 | 105,900 | 122,700 | +16 % |
| 12 | 152,400 | 180,800 | +19 % |
| 8 | 246,800 | 270,400 | +10 %, at the box edge |

What it shows:

- **Any water at all is the big step.** Dry to normal wet-season soil (12 % water)
  more than doubles the ground covered, 44,300 to 98,600 m². This is the model
  switching from a sliding mass to a slurry.
- **How wet the soil is hardly matters.** From wet-season soil to fully saturated,
  0 to 4 inches of rain, adds 9 %. The soil can only hold so much.
- **Storm size above saturation matters only through channel water.** At k=1, 5 to
  10 inches adds 8 %. At k=3 it adds 45 %, and the 10 inch run nears the box edge.
  Everything hangs on k, which is assumed.
- **The stop slope still dominates.** It moves the footprint four to five fold
  (55,000 to 270,000 m²). The biggest storm tested moves it 10 to 20 % at any given
  stop slope. Calibrating the stop slope against a mapped real slide remains the
  priority. The value of k comes second, and only matters for storms well past the
  trigger threshold.

- The stop slope and the water share decide the result. The pile angle does not.
- Water mostly makes it run farther, not wider. Width only picks up at the far end
  where the ground flattens.
- Runs that reach about 1,500 m hit the edge of the 3 km box and would go farther.
  `HALF_BOX_M` sets the box.
- The dry runs are repeatable: `slope15` and `slope15_water0` are the same.

## Soil lookup

`lookup_soils.py` asks the USDA Soil Data Access service for the soil map unit under
each point, takes its main soil, averages the layers down to 1.5 m, and writes:
texture class and the pile angle it implies (standard engineering table), and the
water share from the soil's saturated water content (or from bulk density when that
is missing). Of the 20 slides, 17 are on sandy loams (pile angle 31) and 3 on loams
(29). Water share is 0.32 to 0.37 except on the very bouldery Toecane soil (five
slides, including 8), where it is 0.19.

## Open questions

- The stop slope still has to be chosen. Matching against mapped deposits of past
  slides (the NC Geological Survey's Helene and 2004 inventories) is the way to
  settle it.
- The wet runs could also pick up ground and stream water on the way down
  (r.avaflow's entrainment), which is not turned on.
- The 2.5 ft height in the source table is not used; the volume comes from `acrefeet`.

## License

MIT. See [LICENSE](LICENSE).
