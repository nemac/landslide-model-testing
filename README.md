# Landslide runout modelling for western North Carolina source areas

This project estimates the ground a landslide would cover once it lets go, for a set
of mapped source areas in the Blue Ridge of western North Carolina. It uses the
open-source flow model r.avaflow, run inside GRASS GIS, driven by two Python scripts.
This document explains what is being modelled, how each input is obtained, what the
settings mean, and where the method comes from. It is written for a landslide
specialist who has not used this particular model.

This is screening-level work. The aim is a defensible footprint for each source, not
an engineering design, and the main setting that controls runout has not yet been
calibrated against a mapped event in this terrain. Section 9 says what that would
take.

## 1. What question the model answers

Given a source area, its volume, and the terrain below it, where does the material
go, how far, how deep, and how fast? The model does not ask whether or when the slope
fails. The source areas and their volumes are inputs, taken as given. Rainfall enters
only as a way of adding water to the moving mass, not as a trigger.

## 2. The model

r.avaflow (Mergili et al., 2017; Pudasaini and Mergili, 2019) is a raster-based
simulation of mass flows over terrain. It solves depth-averaged equations of mass and
momentum conservation on the DEM grid, stepping forward in time, with up to three
materials of different density moving together and exchanging momentum. The physics
is the two-phase debris flow model of Pudasaini (2012), generalised to three phases.
It was built for landslides, debris flows, rock avalanches and their interaction with
water bodies, and has been applied to events from the Alps to the Himalaya.

The model has no empirical or statistical component. The same inputs give the same
result every time. It is deterministic, and all of its judgment is in the inputs.

Version 4.0G of r.avaflow is used, compiled against GRASS GIS 8.4 on macOS. The build
is a manual one because the normal GRASS add-on installer fails on this platform;
`install_avaflow.sh` records how it was done.

### How it runs

For each source:

1. A 5 km by 5 km square of terrain is cut from the USGS 1/3 arc-second DEM
   (USGS 3DEP) around the release point and resampled to 10 m cells in NC State
   Plane metres (EPSG:6542). The square was 3 km until October 30, 2026; the lowest
   stop slopes ran off its edge.
2. The whole source volume is placed on the single 10 m cell at the lowest point of
   the source polygon, as a column of material. The lowest point is used so that
   the material starts below any impounded water and runs from the source's toe.
   The column is not physical in its first seconds; the footprint further down the
   path is what the result rests on.
3. r.avaflow runs for 10 minutes of model time, writing a grid every 10 seconds.
4. From the result grids, the script writes one geopackage per source with one
   polygon layer per run (section 7), and a summary table.

## 3. Inputs

| input | source | notes |
|---|---|---|
| terrain | USGS 3DEP 1/3 arc-second DEM | 10 m cells, 5 km box around each release point |
| source polygon and volume | `inputs/sourceareas_dambreach.gpkg` | volume in acre-feet, converted to m³ |
| release point | `inputs/sourceareas_min_elev.gpkg` | the lowest point of each source polygon |
| soil properties | USDA NRCS SSURGO, through the Soil Data Access web service | the map unit under the release point, its dominant component, horizons to 150 cm |
| material settings | derived from the soil, or set by hand | section 4 |
| storm runoff | computed from the DEM and a 24-hour rainfall | section 6 |

Soil properties are retrieved by `lookup_soils.py`, which queries Soil Data Access
for the map unit at each release point, takes the dominant component, and averages
its horizons by thickness down to 150 cm. The properties used are sand, silt and clay
content, saturated water content (`wsatiated_r`), water content at field capacity
(`wthirdbar_r`), water content at wilting point (`wfifteenbar_r`), and the depth of
the deepest described horizon.

## 4. The three material settings

Every run is defined by three numbers about the material. They are the settings that
control the result, and each is given one name throughout this project.

### Stop slope

The ground slope below which the moving material loses its momentum and comes to
rest. r.avaflow calls this the basal friction angle. On ground steeper than this
angle the material accelerates; on flatter ground it decelerates and stops. It
describes the resistance between the base of the flow and the ground, including the
effect of pore water pressure that reduces that resistance in a saturated flow.

Nothing measures this setting. In runout modelling it is obtained by back-analysis:
running documented past events and adjusting the value until the modelled deposit
matches the mapped one (Mergili et al., 2020, is a worked example with r.avaflow).
Typical calibrated values for debris flows are in the range of about 8 to 20
degrees, with lower values for wetter, more mobile flows.

In this project the stop slope is **set by hand and swept**. Every source is run at
**5, 10, 15 and 20 degrees**, crossed with the three storm cases of section 6, twelve
runs per source. Earlier exploratory runs on source 8 also used 8, 12, 18 and 25. The
four levels are meant to bracket what is seen in the Blue Ridge: 20 for a stiff slide
that stops on the hillside, 15 for one that reaches the hollow, 10 for a channelised
debris flow, 5 for a highly mobile, nearly liquefied flow of the kind the 2024
Helene remnants produced. The result is a sensitivity analysis, not a prediction,
until a calibration against a mapped Blue Ridge event is done. The viewer and the
summary table carry every level so the spread is visible for each source.

### Pile angle

The steepest slope at which a loose pile of the material stands without slumping.
r.avaflow calls this the internal friction angle. It describes grain-on-grain
resistance within the moving mass.

In this project the pile angle is **taken from the soil survey**. Sand, silt and
clay percentages give the USDA texture class, and a standard geotechnical table of
typical friction angles by soil type (for example Das, 2010) gives the value: 31
degrees for sandy loam, 29 for loam. Of the 20 sources, 17 are on sandy loams and 3
on loams. A sensitivity test on source 8 varied this setting from 15 to 40 degrees
and found no measurable change in the footprint, so the approximation costs nothing
here.

### Water share

The fraction of the moving mass, by volume, that is water. 0 is dry. r.avaflow
handles this by running its three-material model with the soil as one material and
water as another; the soil keeps the stop slope and pile angle, the water has no
frictional resistance of its own, and the two exchange momentum through drag.

In this project the water share is **taken from the soil survey as the saturated
water content**, averaged over the top 150 cm. For source 8's Toecane bouldery sandy
loam that is 0.19: when every pore is full, 19 percent of the soil volume is water.
The other sources range from 0.19 to 0.37. This represents a slope that fails during
or after heavy rain with its soil fully saturated, which is the triggering condition
for debris flows in this region (Wooten et al., 2008, 2016).

Water share cannot exceed the saturated content from soil alone. Water above that
comes from runoff the flow meets in the hollow, which is section 6.

### Other material properties

Soil grain density is set at 2650 kg/m³, as the model expects (it accounts for pore
space itself). Earlier runs used 2000, the bulk density of loose soil; this reduced
the wet footprint by about a quarter when corrected, because density governs the
interaction between the soil and water phases. Cohesion, viscosity and the other
material parameters are at the model's defaults, which is standard practice for
debris flows at this level of detail.

## 5. Entrainment

Debris flows in the Blue Ridge typically scour the hollow they travel down to bedrock
and arrive with several times their initial volume (Wooten et al., 2008; see Hungr et
al., 2005, for the general process). r.avaflow models this with the erosion model of
Pudasaini and Fischer (2020): the flow erodes the bed at a rate proportional to its
momentum, times a coefficient, and the eroded material joins the flow.

Two settings control it:

- **How deep the flow may dig**, a raster in metres. This project **takes it from the
  soil survey**: the depth of the deepest described horizon for the soil at the
  release point, applied uniformly across the box. For source 8 that is 2.03 m. The
  true depth of colluvium in the hollow is likely greater, since hollows accumulate
  material from their sides; the survey value is a conservative floor.
- **How easily it digs**, the erosion coefficient. r.avaflow takes it as a power of
  ten. It is not measurable and is set by calibration; published r.avaflow
  back-analyses fall roughly between 10⁻⁷ and 10⁻⁶. This project uses **10⁻⁶·⁵** and
  checks it by the growth factor, final volume divided by released volume. Mapped
  Blue Ridge debris flows grew roughly 3 to 10 fold. The current runs on source 8
  grow 1.9 to 2.5 fold, at the low end, so the coefficient is if anything
  conservative.

In the entrainment runs the entrained soil is given the same saturated water share
as the released soil.

## 6. Storm runoff

A slide that fails during a storm meets water already running down the hollow, and
the two mix. r.avaflow can take water in over time at a point through its hydrograph
input. The method here is deliberately the simplest that is physically grounded:

1. **Catchment.** The cells draining to the release point are counted on the DEM
   with GRASS `r.watershed`. For source 8, 244 cells, or 2.4 ha.
2. **Rain rate.** The slide is assumed to occur in the storm's peak hour. In the SCS
   Type II 24-hour distribution, used for design storms in inland North Carolina,
   about 45 percent of the 24-hour total falls in that hour (USDA NRCS, 1986). A 5
   inch storm gives 2.25 inches in the peak hour; a 10 inch storm, 4.5.
3. **Runoff.** The soil is already saturated, so all peak-hour rain is taken as
   runoff.
4. **Inflow.** Rain rate times catchment, held steady for the run: 0.39 m³/s for the
   5 inch storm and 0.77 for the 10 inch, entering as water at the release cell.

The 5 inch storm is used because about 125 mm in 24 hours is the widely used working
threshold for debris flow initiation in western North Carolina, with lower totals
sufficient when the ground is already wet (Wooten et al., 2008, 2016). The 10 inch
storm is an extreme case, in the range of the 2004 and 2024 hurricane remnants.

What this leaves out: rain falling faster than the ground can absorb before
saturation, drainage during the storm, and water arriving from upslope outside the
DEM-derived catchment. For a 24-hour storm on a saturated hillside these are small
relative to the assumptions already made.

### The hydrograph itself

The storm enters the model as an r.avaflow hydrograph: a text table of time against
inflow, one row every 10 seconds for the 10 minute run, with the water inflow held at
the rate computed above and the soil materials at zero. It is written by
`avaflow_run.py` into the run folder as `storm_hydrograph.txt`, together with
`storm.json`, which records the catchment area, the peak-hour rain rate and the
inflow so the numbers behind every storm run can be checked. The hydrograph point is
the release cell, given to r.avaflow through `hydrocoords`. The viewer draws the same
table as the first panel of a storm run's charts: a flat line at the inflow rate and
a rising line for the water added so far.

A steady inflow is a simplification. Real runoff from a 2 to 3 hectare hollow rises
and falls with the rain over tens of minutes. Holding it at the peak-hour rate for
the 10 minute run assumes the slide lets go at the height of the storm, which is the
conservative case and the one the regional threshold describes.

Note on implementation: r.avaflow 4.0G in its default hydrograph mode reads the
hydrograph's height column as a volumetric rate in m³/s added at the point each time
step (`HYDADD = 2` in the source). The script writes it that way.

## 7. Outputs

All outputs go to `outputs/`, which is not kept in version control.

**Geopackages.** `landslide_<fid>_avaflow.gpkg`, one per source. Layers:

| layer | content |
|---|---|
| `deposit_<run>` | every cell the material passed through at a depth over 1 cm, as polygons banded by peak depth: 1–5, 5–20, 20–50, 50–100, over 100 cm. Attributes carry the run's settings, area and volume per band |
| `arrival_<run>` | when the material first reached each cell, as polygons in 5 minute bins |
| `hydrograph_<run>` | for storm runs, the inflow point with storm total, catchment area, peak rain rate and inflow |

**Summary table.** `landslide_avaflow_summary.csv`, one row per source and run:
settings, ground covered, farthest reach from the release point, peak depth, deposit
thickness at rest, released and entrained volume, growth factor, storm total and storm
water added.

**Soil table.** `landslide_soils.csv`, one row per source: map unit, component,
texture, pile angle, saturated, field capacity and wilting point water contents, soil
depth.

**Figures.** `plots/<source>_<run>_review.png`, four panels per run in the style of a
dam-break review: material in motion against time, peak depth down the valley,
arrival time down the valley, and area by depth band. `plots/<source>_compare.png`
overlays all runs of a source. Distance down the valley is measured along the path
the material took, traced downhill from the release point.

## 8. The run matrix and what the exploratory runs showed

Every source is run twelve ways: stop slope 5, 10, 15 or 20 degrees, each dry of
storm runoff or with the 5 inch or 10 inch storm flowing in, always with the soil's
saturated water share, the soil's pile angle, entrainment on, and the full volume.
Run names say the settings, for example `stopslope10_soilsat_entrain_storm5in`. The
results for all sources are in the summary table and the web viewer.

Before the matrix, exploratory runs on source 8 (fid 8, Toecane bouldery sandy loam,
448 m³ released, 3 km box) established the ranking of the settings:

| finding | numbers from source 8 |
|---|---|
| the stop slope dominates | ground covered 55,000 m² at 25° against 247,000 m² at 8°, saturated soil, no entrainment |
| any water at all roughly doubles the footprint | 44,300 m² dry against 98,600 m² at the soil's normal wet-season water content |
| how wet the soil is below saturation hardly matters | under 10 % change from wet-season to saturated |
| the pile angle has no effect | no measurable change between 15° and 40° |
| entrainment reshapes more than it extends | +4 % area, but the deposit fills and spreads across the hollow instead of running as a thin streak |
| storms add through entrainment | at stop slope 15: 79,900 m² dry of runoff, 85,800 m² with the 5 inch storm, 92,200 m² with the 10 inch storm; growth 1.9×, 2.3×, 2.5× |

The entrainment deposits match the form of mapped Blue Ridge debris flow deposits
better than the runs without it.

## 9. Limitations and what comes next

- **The stop slope is uncalibrated.** This is the single largest uncertainty, and the
  model offers the tools to fix it: the `impactarea` and `hdeposit` inputs take a
  mapped deposit and score the fit. Two or three mapped Blue Ridge debris flows with
  known source volumes, run at several stop slopes, would give a defensible value or
  range for this terrain. The NC Geological Survey's inventories from the 2004 and
  2024 events are the natural source.
- **The erosion coefficient is likewise uncalibrated**, and interacts with the stop
  slope: more entrainment runs farther, so the two should not be tuned together on
  one event. Calibrate the stop slope with entrainment off, then entrainment.
- **The release geometry** is a column on one cell. It is a reasonable way to start
  the material at the toe, but it is not a slab failure, and depths in the first
  50 m of the path should not be read literally.
- **The 5 km box** truncates runs beyond about 2.5 km from the release point. The 5
  degree runs are the ones to check against it; the summary's farthest-reach column
  shows when a run is near the edge.
- **Storm runoff** rests on the peak-hour assumption and on the DEM catchment. Both
  are stated and easily changed.
- **Volume** is taken as the full source. Partial failures are not modelled; the full
  volume is the conventional design case.

## 10. Running it

```
python3 lookup_soils.py                 # once: soil table for every source
python3 avaflow_run.py                  # every run in RUNS for every source
python3 avaflow_run.py 8                # source 8 only
python3 avaflow_run.py 8 --runs stopslope15_soilsat_entrain_storm5in
python3 avaflow_run.py --collect        # rebuild geopackages and summary from runs on disk
python3 avaflow_plots.py 8              # review figures for source 8
```

Runs already on disk are kept and skipped; `--redo` reruns them. The stop slopes and
storms in the matrix are the two tuples `STOP_SLOPES` and `STORMS_IN` at the top of
`avaflow_run.py`.

Requirements: GRASS GIS 8.4 at `/Applications/GRASS-8.4.app`, r.avaflow 4.0G built by
`install_avaflow.sh`, and a Python with `numpy rasterio fiona shapely pyproj
matplotlib`. The two source geopackages go in `inputs/` and are not kept in version
control. Each r.avaflow run takes two to three minutes.

All settings are at the top of `avaflow_run.py`. The list `RUNS` holds one entry per
run; run names say the settings: `stopslope15_soilsat_entrain_storm5in` is stop slope
15, pile angle and water share from the saturated soil, entrainment on, 5 inch
storm. A full account of every r.avaflow input, in plain language, is in
`docs/r_avaflow_inputs.md`.

## References

Das, B. M. (2010). *Principles of Geotechnical Engineering*, 7th ed. Cengage. Typical
friction angles by soil type.

Hungr, O., McDougall, S., and Bovis, M. (2005). Entrainment of material by debris
flows. In Jakob, M. and Hungr, O. (eds), *Debris-flow Hazards and Related
Phenomena*, Springer, 135–158.

Iverson, R. M. (1997). The physics of debris flows. *Reviews of Geophysics*, 35(3),
245–296.

Mergili, M., Fischer, J.-T., Krenn, J., and Pudasaini, S. P. (2017). r.avaflow v1, an
advanced open-source computational framework for the propagation and interaction of
two-phase mass flows. *Geoscientific Model Development*, 10, 553–569.

Mergili, M., Jaboyedoff, M., Pullarello, J., and Pudasaini, S. P. (2020). Back
calculation of the 2017 Piz Cengalo–Bondo landslide cascade with r.avaflow: what we
can do and what we can learn. *Natural Hazards and Earth System Sciences*, 20,
505–520.

Mergili, M. and Pudasaini, S. P. r.avaflow: the mass flow simulation tool.
https://www.landslidemodels.org/r.avaflow/ (software and manual, version 4.0G).

Pudasaini, S. P. (2012). A general two-phase debris flow model. *Journal of
Geophysical Research: Earth Surface*, 117, F03010.

Pudasaini, S. P. and Fischer, J.-T. (2020). A mechanical erosion model for two-phase
mass flows. *International Journal of Multiphase Flow*, 132, 103416.

Pudasaini, S. P. and Mergili, M. (2019). A multi-phase mass flow model. *Journal of
Geophysical Research: Earth Surface*, 124, 2920–2942.

USDA Natural Resources Conservation Service (1986). *Urban Hydrology for Small
Watersheds*, Technical Release 55. Rainfall distributions, Type II.

USDA Natural Resources Conservation Service. Soil Survey Geographic Database
(SSURGO) and Soil Data Access web service. https://sdmdataaccess.sc.egov.usda.gov/

U.S. Geological Survey. 3D Elevation Program, 1/3 arc-second DEM.
https://www.usgs.gov/3d-elevation-program

Wooten, R. M., Gillon, K. A., Witt, A. C., Latham, R. S., Douglas, T. J., Bauer,
J. B., Fuemmeler, S. J., and Lee, L. G. (2008). Geologic, geomorphic, and
meteorological aspects of debris flows triggered by Hurricanes Frances and Ivan
during September 2004 in the Southern Appalachian Mountains of Macon County, North
Carolina (southeastern USA). *Landslides*, 5, 31–44.

Wooten, R. M., Witt, A. C., Miniat, C. F., Hales, T. C., and Aldred, J. L. (2016).
Frequency and magnitude of selected historical landslide events in the Southern
Appalachian Highlands of North Carolina and Virginia: relationships to rainfall,
geological and ecohydrological controls, and effects. In Greenberg, C. H. and
Collins, B. S. (eds), *Natural Disturbances and Historic Range of Variation*,
Springer, 203–262.
