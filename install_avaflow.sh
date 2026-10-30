#!/bin/bash
# Install r.avaflow 4.0G into GRASS GIS 8.4 on macOS, the way it had to be done
# for this project (October 2026). Run once:  bash install_avaflow.sh
#
# What it does
#   1. downloads the r.avaflow 4.0G source zip into avaflow_download/ and unpacks it
#   2. compiles the C program (r.avaflow.main) against the GRASS 8.4 app's libraries
#      with the system C compiler. g.extension cannot do this on macOS: its link step
#      pulls in GRASS's gmath library, whose openblas/gfortran dependencies fail to
#      load. main.c does not use gmath, so it is left out of the link.
#   3. copies the program and the five python scripts into the macOS add-on folder
#      ~/Library/GRASS/8.4/Addons (not ~/.grass8/addons, which GRASS on macOS ignores)
#   4. checks that GRASS's own python has Pillow and numpy (r.avaflow needs them)
#   5. checks that r.avaflow answers from inside GRASS
#
# Needs: GRASS-8.4.app in /Applications, the Xcode command line tools (cc), curl, unzip.
# The R-based plots (-v flag) are not set up; this project does not use them.
set -e
HERE=$(cd "$(dirname "$0")" && pwd)
GB=/Applications/GRASS-8.4.app/Contents/Resources
ADDONS=~/Library/GRASS/8.4/Addons
URL=https://www.landslidemodels.org/r.avaflow/software/r.avaflow.40G.zip
DL=$HERE/avaflow_download
BUILD=$HERE/avaflow_build
SRC=$DL/r.avaflow.40G

[ -d "$GB" ] || { echo "GRASS-8.4.app not found in /Applications"; exit 1; }

echo "1. source"
mkdir -p "$DL" "$BUILD"
[ -f "$DL/r.avaflow.40G.zip" ] || curl -L -o "$DL/r.avaflow.40G.zip" "$URL"
[ -d "$SRC" ] || unzip -q "$DL/r.avaflow.40G.zip" -d "$DL"

echo "2. compile r.avaflow.main (without gmath)"
cp "$SRC/r.avaflow.main/main.c" "$BUILD/main.c"
cc -O2 -w -DPACKAGE='"grassmods"' -I"$GB/include" -L"$GB/lib" -Wl,-rpath,"$GB/lib" \
   "$BUILD/main.c" -lgrass_gis.8.4 -lgrass_raster.8.4 -lgrass_segment.8.4 -lm \
   -o "$BUILD/r.avaflow.main"

echo "3. install into $ADDONS"
mkdir -p "$ADDONS/bin" "$ADDONS/scripts" "$ADDONS/docs/html"
cp "$BUILD/r.avaflow.main" "$ADDONS/bin/r.avaflow.main"; chmod +x "$ADDONS/bin/r.avaflow.main"
for m in r.avaflow/r.avaflow.40G r.lakefill/r.lakefill r.scarp/r.scarp \
         r.avaflow.mult/r.avaflow.mult r.avaflow.background/r.avaflow.background; do
    n=$(basename "$m")
    cp "$SRC/$m.py" "$ADDONS/scripts/$n"; chmod +x "$ADDONS/scripts/$n"
    cp "$SRC/$m.html" "$ADDONS/docs/html/" 2>/dev/null || true
done

echo "4. python packages inside GRASS's own python"
"$GB/bin/python3" -c "import PIL, numpy" 2>/dev/null || "$GB/bin/python3" -m pip install Pillow numpy

echo "5. check"
GRASS=/usr/local/bin/grass
[ -x "$GRASS" ] || GRASS="$GB/bin/grass"
"$GRASS" --tmp-project EPSG:6542 --exec r.avaflow.40G --help 2>&1 | head -3

echo
echo "r.avaflow installed. The run script avaflow_run.py also needs, in the python you run it with:"
echo "    pip install numpy rasterio fiona shapely pyproj"
