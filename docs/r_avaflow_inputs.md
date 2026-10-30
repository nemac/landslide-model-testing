# r.avaflow inputs, explained for a GIS user

r.avaflow (version 4.0G, run inside GRASS GIS 8.4) is a raster flow model. You give
it a terrain raster and a raster of how much material starts moving in each cell. It
then pushes that material downhill, cell to cell, for a set number of seconds, and
writes rasters of where it went and how deep it got.

Everything below is every input the module accepts, in plain words. The official
module help has one line per parameter and sends you to
<https://www.landslidemodels.org/r.avaflow/> for the rest, so this page pulls both
together. Where this project sets a parameter, it says so. Where the official text
is missing or unclear, it says that too.

**Translation key.** Geology words that come up and what they mean here:

| the model says | what it means |
|---|---|
| mass flow | anything that slides or flows downhill as a body: landslide, debris flow, rock avalanche, snow avalanche |
| release | the material that starts moving, and where. A raster of starting thickness in metres |
| phase | a material. The model can track one material, or up to three that move together (for example rock, mud and water) |
| flow height | thickness of moving material in a cell, metres, measured straight up |
| deposit | material that has stopped. The final flow height raster |
| entrainment | the flow scooping up ground as it passes and getting bigger |
| friction angle | how much grip a material has, written as a slope angle. A pile of it stands up to about that slope. Bigger angle, stiffer material |
| internal friction angle | grip inside the material, grain on grain. The README calls this the pile angle |
| basal friction angle | grip between the bottom of the flow and the ground. The README calls this the stop slope. On ground flatter than this angle the flow drags and stops |
| cohesion | stickiness that holds material together regardless of pressure. Wet clay has it, loose sand does not |
| viscosity | thickness of a liquid in the honey sense |
| hydrograph | a table of how much material arrives at a point over time, instead of a release raster |
| CFL, limiter | settings of the maths that steps the model forward. Leave alone unless the run crashes |

## 1. Phases: one material or three

`phases=1` tracks one material. `phases=3` tracks up to three, called PHASE 1, 2 and 3
(P1, P2, P3). The model does not label them solid or fluid; what they are is decided
by the densities and frictions you give them. Density must go P1 heaviest, P3
lightest, so in practice P1 is the ground material, P2 a fine middle material, and P3
water. Any of the three can be left empty to run two.

Every comma-separated parameter list below is given once per phase. For `phases=1`
you give one set. For `phases=3` you give three, in P1, P2, P3 order, grouped as the
parameter describes.

**This project.** Dry runs use `phases=1`. Wet runs use `phases=3` with P1 the ground
material, P2 empty, and P3 water.

## 2. The command this project runs

From `avaflow_run.py`, one r.avaflow run looks like this (dry, one phase):

```
r.avaflow.40G -e -k prefix=ls08 elevation=dem hrelease=hrelease
    phases=1 density=2650 friction=31,15,0
    time=10,600 cellsize=10
    thresholds=0.01,10000,10000,0.01,0.000001
    aoicoords=<north>,<south>,<east>,<west>
```

and like this for a wet run (three phases, middle one empty, 19 % water):

```
r.avaflow.40G -e -k prefix=ls08 elevation=dem hrelease=hrelease
    phases=3 rhrelease1=0.81
    density=2650,1850,1000
    friction=31,31,0,15,15,0,0,0,0
    time=10,600 cellsize=10
    thresholds=0.01,10000,10000,0.01,0.000001
    aoicoords=<north>,<south>,<east>,<west>
```

Each piece is explained in the sections that follow. Everything not on the command
line is at its default.

## 3. Flags

Flags are single letters switched on with a dash.

| flag | official text | plain words | this project |
|---|---|---|---|
| `-e` | Model execution | Actually run the model. If you give neither `-e` nor `-v`, `-e` is assumed | on |
| `-k` | Keep result GRASS raster maps | Without it the result rasters are deleted from the GRASS mapset at the end, leaving only the ASCII copies in the results folder | on |
| `-m` | Multiple model runs | Run the model many times over a range of parameter values and build "impact indicator" rasters showing how often each cell was hit. Uses `sampling` and `cores` | off |
| `-a` | Map plots of pressure and kinetic energy | Also write velocity, pressure and kinetic energy rasters, not just flow height | off |
| `-t` | Map plots of impact wave or tsunami height | For a landslide hitting a lake: write rasters of the wave height. Three phases only | off |
| `-v` | Evaluation and visualization | Make the R plots, maps and animations. Needs R installed; not set up on this machine | off |

## 4. Run setup

| parameter | official text | plain words | default | this project |
|---|---|---|---|---|
| `prefix` | Prefix for output files and folders | A short name stuck on the front of every output. `ls08` gives `ls08_results/`, `ls08_hflow_max`, and so on | required | `ls<fid>` |
| `cellsize` | Cell size in metres | Resolution to run at. The inputs are resampled to this. Smaller is slower: halving it quadruples the cells and roughly doubles the time steps | region cell size | 10 |
| `aoicoords` | Set of coordinates delineating area of interest (N,S,E,W) | The run extent, as north, south, east, west edges in map units. r.avaflow starts from the GRASS project's default region, not the current one, so this must be given | project default region | the 3 km box round the slide |
| `phases` | Number of phases (1 = single-phase model, 3 = multi-phase model) | One material or up to three. See section 1 | 1 | 1 dry, 3 wet |
| `gravity` | Gravity (m/s2) | Leave alone on Earth | 9.81 | default |
| `limiter` | Numerical limiter (1 = Minmod, 2 = Superbee, 3 = Woodward, 4 = van Leer) | Which smoothing rule the maths uses between cells. Only touch if a run goes unstable | 1 | default |
| `cores` | Number of cores to be used for multiple model runs | CPU cores for `-m` runs | 1 | not used |

### Control switches

Each turns a piece of physics on or off.

| parameter | official text | plain words | default | this project |
|---|---|---|---|---|
| `clayers` | Layer control (0 = off, 1 = on) | Off: the phases are mixed through the flow depth. On: they ride in layers, P1 at the bottom, P3 on top. In layer mode `phases` is ignored and the friction numbers change meaning | 0 | default |
| `ctopo` | Input and output of flow heights and velocities (0 = vertical, 1 = slope-normal) | Whether thickness is measured straight up (as a GIS raster would) or at right angles to the ground | 0 | default |
| `csurface` | Surface control (0 = off, 1 = edge control, 2 = force balancing) | Corrections for a flow entering a reservoir or lake. Leave off unless modelling that | 0 | default |
| `centrainment` | Entrainment control (0 = off, 1 = on) | Let the flow scoop up ground and grow. Needs an entrainment coefficient (section 6) and optionally a raster of how deep it may dig (`hentrmax`) | 0 | default (off) |
| `cstopping` | Stopping control (0 = off, 1-3 = type of approach) | Force the whole flow to stop once it has slowed down enough. 1: stop when kinetic energy drops to a fraction of its peak. 2: same with momentum. 3: stop when no cell has pressure above a threshold. The fraction or threshold is the second value of `entrainment`. Off means material stops only where friction stops it | 0 | default (off) |
| `cdispersion` | Dispersion control (0 = off, 1 = on) | Extra spreading physics for flows entering water | 0 | default |
| `cmelt` | Melt control (0 = off, 1 = on) | Ice and snow melting from frictional heat. Uses `melting` | 0 | default |

## 5. Input rasters

All of these are names of GRASS raster maps in the current mapset. The run script
imports GeoTIFFs with `r.in.gdal` first.

### Terrain and release

| parameter | official text | plain words | this project |
|---|---|---|---|
| `elevation` | Name of elevation raster map | The DEM, metres. The only input that is always required | `dem`, 10 m, from the USGS 1/3 arc-second DEM |
| `hrelease` | Name of release height raster map | Thickness of material that starts moving, metres, in every cell. Zero or no-data where nothing moves. With three phases this is the total and `rhrelease1` says how it splits | `hrelease`: the whole slide volume on the one cell at the release point |
| `rhrelease1` | Ratio(s) of PHASE 1 release height (comma-separated) | With three phases and one `hrelease`: the share of it that is P1, 0 to 1. The rest is P3 (water). 0.81 means 81 % ground, 19 % water | 1 minus the water share |
| `hrelease1`, `hrelease2`, `hrelease3` | Name of PHASE 1/2/3 release height raster map | Instead of `hrelease` plus a ratio, give a separate thickness raster for each phase | not used |
| `vhrelease` | Variation of release height (comma-separated) | For `-m` runs only: a range to vary the release thickness over | not used |
| `trelease` | Release time raster map | Seconds after the start at which each cell lets go. Lets different parts release at different times. Without it everything goes at second zero | not used |
| `trelstop` | Release hydrograph stop time raster map | When a release that is fed over time stops | not used |
| `tslide` | Time of initial sliding raster map | Seconds during which the material first moves as a rigid block before it starts to flow. Used with `slidepar` | not used |
| `tstop` | Stopping time raster map | Force the flow to stop in each cell at a given second | not used |
| `zones` | Zones raster map | Integer zones, used by the `-m` evaluation to report results by area | not used |

### Observed data, for checking a run

| parameter | official text | plain words |
|---|---|---|
| `impactarea` | Name of observed impact area raster map | A raster of where a real past slide went, 1 inside, 0 outside. The model compares its result against it and scores the fit |
| `hdeposit` | Name of observed deposit height raster map | Mapped deposit thickness of a real slide, metres, for the same comparison |

This project does not use these yet. They are how you would calibrate the stop slope
against mapped western North Carolina slides.

### Starting speed

| parameter | plain words |
|---|---|
| `vinx`, `viny` | Rasters of starting velocity east-west and north-south, m/s, if the material is already moving at second zero. Phase versions `vinx1`...`viny3` do the same per phase. Not used here: everything starts at rest |

### Entrainment rasters

| parameter | plain words |
|---|---|
| `hentrmax` | How deep the flow may dig into the ground in each cell, metres. With three phases, `rhentrmax1` gives the P1 share, like `rhrelease1` |
| `hentrmax1`, `hentrmax2`, `hentrmax3` | The same per phase |
| `vhentrmax` | A range for `-m` runs |
| `centr` | Entrainment coefficient as a raster, to vary it across the map instead of one number |

None used here, since entrainment is off.

### Material properties as rasters

Every material number in section 6 can instead be a raster, so the value changes
across the map. Useful when the ground changes (say, rock to soil) along the path.

| parameter | plain words |
|---|---|
| `phi1`, `phi2`, `phi3` | Internal friction angle (pile angle) per phase, degrees |
| `delta1`, `delta2`, `delta3` | Basal friction angle (stop slope) per phase, degrees |
| `addfri1`, `addfri2`, `addfri3` | The extra friction number per phase (section 6, `friction`) |
| `coh1`, `coh2`, `coh3` | Cohesion per phase |
| `ny1`, `ny2`, `ny3` | Viscosity per phase |
| `cdeform` | Deformation coefficient of P1 |
| `zfrag` | Fragmentation zones |
| `ambdrag` | Air drag coefficient |
| `ctrans12`, `ctrans13`, `ctrans23` | Rate at which one phase turns into another, per pair |

None used here. This project gives single numbers, which apply everywhere.

## 6. Material parameters

These are the numbers that decide how far and how wide the flow goes. Each is a
comma-separated list: one value for one phase, three (or multiples of three) for
three phases, in P1, P2, P3 order.

### `density`

Official: Density parameters (comma-separated). Units kg/m³. One per phase, P1
heaviest. For granular material use the grain density, not the bulk density of the
loose pile.

Default `2700` (one phase) or `2700,1850,1000` (three). This project: `2650` for
the soil grains (runs before 29 Oct 2026 used 2000, the bulk density of loose soil),
and `2650,1850,1000` for wet runs, the middle value being an unused
placeholder since P2 is empty.

### `friction`

Official: Friction parameters (comma-separated). This is the one that matters most.

One phase, three values:

1. internal friction angle, degrees (pile angle). If it is set below the basal angle the model raises it to match
2. basal friction angle, degrees (stop slope)
3. extra friction. 0 means none. A positive number is a fluid friction number like
   Manning's n, giving drag that grows with speed. A negative number such as `-1000`
   is a turbulent friction number of 1000, a Voellmy-type drag

Three phases, nine values, grouped by type then phase:

1 to 3. internal friction angle of P1, P2, P3
4 to 6. basal friction angle of P1, P2, P3
7 to 9. extra friction of P1, P2, P3

Water (P3) gets 0 for both angles since it has no grip of its own.

Default `35,20,0.0` and `35,17.5,0,20,10,0,0,0,0`. This project: pile angle from the
soil lookup (or 35), stop slope swept across runs (8 to 25 in the soil runs), extra
friction 0. For wet runs the P2 angles are copied from P1 and the P3 angles are 0.

### `cohesion`

Official: Cohesion parameters (comma-separated). Units N/m². Stickiness holding the
material together. Default `0.0` per phase. Not changed here.

### `viscosity`

Official: Viscosity parameters (comma-separated). Given as log10 of kinematic
viscosity in m²/s, so `-7` means 0.0000001. Only matters for the slow-flow models
turned on through `slomo`. Default `-7.0` per phase. Not changed here.

### `deformation`

Official: Deformation parameters (comma-separated). 0 to 1 per phase. 1 means the
material deforms freely as it flows, 0 means it is locked and slides as a block.
Default `1.0`. Not changed here.

### `slidepar`

Official: Parameters for initial sliding (exponent for weighting, coefficient for
deformation). Used with the `tslide` raster: the flow starts as a sliding block and
turns into a flow over `tslide` seconds. Two values per phase: an exponent for how
quickly the block behaviour fades (0 constant, 1 linear, 2 fast at first, 0.5 slow
at first) and the starting block fraction. Default all zeros, meaning no block
phase. Not used here.

### `shearing`

Official: Strength of frictional energy loss in shearing. One number. The online
manual's table for it is empty. Default `0.0`. Not used here.

### `fragmentation`

Official: Fragmentation parameters (comma-separated). Two numbers, for rock breaking
up as it falls. The online manual's table for it is empty. Default `0.0,0.0`. Not
used here.

### `ambient`

Official: Ambient drag coefficient. One number: air resistance, applied to the
flow's front. Default `0.0`. Not used here.

### `entrainment`

Official: Entrainment and stopping parameters (comma-separated). Two numbers, and
despite the name the second is about stopping, not entrainment:

1. entrainment coefficient as log10, used only when `centrainment=1`. Bigger
   (closer to zero) scoops up more ground. `-7` is effectively nothing
2. stopping threshold, used only when `cstopping` is 1, 2 or 3. For types 1 and 2 a
   fraction of the peak energy or momentum (0.05 means stop when down to 5 %). For
   type 3 a pressure in Pa

Default `-7.0,0.0`. Not used here since both switches are off.

### `drag`

Official: Drag parameters (comma-separated). Three phases only: how the materials
pull on each other, for example water dragging ground along. Six numbers: a drag
flux parameter in m/s, an exponent for fluid-like drag, an exponent for how drag
scales with the solid fraction, the terminal settling velocity of grains in m/s, a
particle Reynolds number, and 1 or 2 for linear or quadratic drag. Default
`1,3,1,0.1,1,1`. Not changed here.

### `virtualmass`

Official: Virtual mass parameters (comma-separated). Three phases only: three
numbers for the extra inertia a grain feels when it accelerates through water.
Default `10,0.12,1`. Not changed here.

### `transformation`

Official: Phase transformation parameters (comma-separated). Three phases only: how
fast P1 turns into P2, P1 into P3, P2 into P3, as log10 of a rate, 0 for none, minus
sign to reverse direction. Models rock grinding to mud, or ice melting to water.
Default `0.0,0.0,0.0`. Not changed here.

### `melting`

Official: Temperature evolution and ice melting parameters (comma-separated). Five
numbers: landslide, air and ground temperature in °C, the share of frictional heat
that goes into melting, and the sliding fraction at the base. Only with `cmelt=1`.
Default `0,0,0,0.2,0.5`. Not used here.

## 7. Feeding material in over time

Instead of, or as well as, a release raster, material can arrive at a point over
time from a table.

| parameter | official text | plain words |
|---|---|---|
| `hydrograph` | Path(es) to hydrograph file(s) | Text file(s): time in seconds, then flow height and velocity per phase at that time. One file per input point |
| `hydrocoords` | Pairs of coordinates of hydrograph(s) (x1, y1, x2, y2, ...) | Where each hydrograph enters the map, map units. Required with `hydrograph` |
| `adaptograph` | Path(es) to adaptograph file(s) | A table that changes model settings during the run at set times |
| `frictiograph` | Path(es) to frictiograph file(s) | A table that changes the friction values during the run at set times, for material that softens or stiffens as it goes |
| `transformograph` | Path(es) to transformograph file(s) | A table that changes the phase transformation rates during the run |

None used here.

## 8. Many runs at once

With `-m` the model runs many times over a spread of parameter values.

| parameter | official text | plain words |
|---|---|---|
| `sampling` | Type of parameter sampling (positive number = random, 0 = controlled, negative number = OAT) | Positive: that many random draws across the ranges. 0: an even grid across the ranges. Negative: vary one parameter at a time, that many steps each. Default 100 |
| `cores` | Number of cores | CPU cores to run them on |

For `-m`, each parameter list carries a range instead of a value (pairs of
low and high, which is why the defaults in the code double up for `-m`). The
output is a set of impact indicator rasters: the share of runs that reached each
cell. This project does its sweep by hand instead, one named run per setting, so
each result is a separate layer.

## 9. Time and numerics

### `time`

Official: Time interval (s), stop for writing output (s). Two numbers: how often to
write a raster, and when to stop, both in seconds. `10,600` writes a raster every
10 model seconds and stops at 10 model minutes. This project: `10,600`.

### `cfl`

Official: CFL criterion, initial time step length (s). Two numbers that control how
big a time step the maths may take. The first must be 0.5 or less, default 0.4.
The second is the step used when the first cannot be applied, such as the very first
step. Only change if a run blows up. Not changed here.

### `slomo`

Official: Parameters for slow motion (comma-separated). Three numbers. The first is
a time scaling factor: 1 for ordinary flows; a large number such as 86400 switches
to a slow creeping-flow model with output per day; a negative number is a glacier
mode. The other two tune that slow model. Default `1,1,1`. Not changed here.

### `thresholds`

Official: Lower thresholds for display of flow height, velocity, kinetic energy, and
pressure (comma-separated). Five numbers:

1. minimum flow height to show in the output rasters, metres. Below it a cell is
   written as no flow
2. minimum kinetic energy to show, J
3. minimum pressure to show, Pa
4. minimum flow height for a cell's velocity to be reported, metres
5. minimum flow height for the simulation itself, metres. Thinner than this is set
   to zero as the model runs

The first four only affect what is written. The fifth affects the physics.

Default `0.1,10000,10000,0.1,0.000001`. This project:
`0.01,10000,10000,0.01,0.000001`, so anything over 1 cm shows in the output.

## 10. Plots and evaluation

All of these only matter with `-v`, which needs R and is not set up here.

| parameter | plain words |
|---|---|
| `profile` | Pairs of x,y map coordinates for a line along which to draw a cross-section plot |
| `ctrlpoints` | Pairs of x,y map coordinates for points at which to report arrival time and flow height |
| `reftime` | Observed arrival time at each control point, seconds, to compare against |
| `phexagg` | Vertical exaggeration of flow height in the profile plots |
| `orthophoto` | Path to an aerial image GeoTIFF to draw under the maps |
| `visualization` | A list of settings for the maps and animations |

## 11. What comes out

Everything lands in `<prefix>_results/` in the working directory, with ASCII grid
copies in `<prefix>_ascii/`. With `-k` the same rasters stay in the GRASS mapset.
Names are `<prefix>_<quantity><timestep>` for each output interval, plus `_max` for
the highest value over the run and `_fin` for the value at the end.

| raster | plain words | this project |
|---|---|---|
| `hflow<t>` | flow height at time step t, metres | not kept |
| `hflow_max` | the deepest the material got in each cell at any time. The footprint of everywhere it went | the deposit layers in the geopackages |
| `hflow_fin` | how thick it lies at the end. The deposit | `resting_thickest_m` in the summary |
| `vflow<t>`, `vflow_max` | speed, m/s | exported, not yet used |
| `tflow`, `pflow` | kinetic energy and pressure, only with `-a` | not made |
| `basechange<t>`, `basechange_fin` | ground dug out (negative) or laid down (positive), metres. Only meaningful with entrainment | not used |
| `treach` | seconds until each cell was first reached | not used |
| `vfront`, `r1front`, `r3front` | speed and phase mix at the flow front | not used |
| `elev_mod` | the DEM after the event | not used |
| `tsun<t>` | wave height, three phases with `-t` | not made |

One thing to know: r.avaflow resets the GRASS computational region to a single cell
when it finishes. The run script therefore reads the ASCII grids rather than
exporting from GRASS, and you should run `g.region` again before doing anything else
in that mapset.

## 12. Which inputs actually matter for this project

In order of how much they change the footprint on slide 8:

1. **basal friction angle** (stop slope, `friction` entry 2 or 4 to 6). The main
   control on how far it runs. Nothing measures it; it is calibrated against mapped
   past slides.
2. **water share** (`rhrelease1`, with `phases=3`). More water, much longer runout.
   Set from the soil's pore space.
3. **release volume** (`hrelease`). From the source area table.
4. **cell size and box** (`cellsize`, `aoicoords`). 10 m and 3 km. Runs over about
   1.5 km hit the box edge and are cut short.
5. **internal friction angle** (pile angle, `friction` entry 1 or 1 to 3). Made no
   difference on slide 8 between 15 and 40 degrees.

Everything else is at its default.

## Sources

- Module help embedded in `r.avaflow.40G` (the one-line descriptions quoted as
  "official text" above). Local copy in `avaflow_download/r.avaflow.40G/r.avaflow/`.
- Default values from the module's source, in the same folder.
- Parameter meanings from the r.avaflow 4.0 web manual at
  <https://www.landslidemodels.org/r.avaflow/direct.php>. Its tables for `shearing`
  and `fragmentation` are empty, and it does not document `-e`; those entries above
  come from the source code.
- Mergili, M. and Pudasaini, S. P., r.avaflow, <https://www.landslidemodels.org/r.avaflow/>.
