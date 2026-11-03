#!/bin/bash
# Runs ON the machine (sent over by aws/setup.sh). Ubuntu 22.04.
# Installs GRASS, builds r.avaflow 4.0G the same way install_avaflow.sh does on the Mac,
# installs the Python packages with pip, builds tippecanoe, sets git up with the deploy
# key and clones the repo. Safe to run again.
set -e
export DEBIAN_FRONTEND=noninteractive
REPO=git@github.com:nemac/landslide-model-testing.git
DIR=$HOME/landslide-model-testing

echo "== packages"
sudo apt-get update -q
# Ubuntu 22.04 ships GRASS 7.8 and the ubuntugis add-on repository does not fit it, so
# GRASS 8.4 is built from source below; these are what that build and r.avaflow need
sudo apt-get install -y -q build-essential flex bison git rsync unzip curl python3-dev python3-pip python3-numpy python3-pil \
  libgdal-dev gdal-bin libproj-dev proj-bin proj-data libgeos-dev libsqlite3-dev zlib1g-dev libbz2-dev libzstd-dev \
  libreadline-dev libncurses-dev libtiff-dev libpng-dev libfreetype-dev libblas-dev liblapack-dev

echo "== GRASS 8.4"
if ! grass --version 2>/dev/null | grep -q "GRASS GIS 8.4"; then
  GV=8.4.1
  mkdir -p $HOME/grass_src && cd $HOME/grass_src
  [ -f grass-$GV.tar.gz ] || curl -sL -o grass-$GV.tar.gz https://grass.osgeo.org/grass84/source/grass-$GV.tar.gz
  [ -d grass-$GV ] || tar xzf grass-$GV.tar.gz
  cd grass-$GV
  ./configure --with-cxx --with-gdal --with-proj-share=/usr/share/proj --with-geos --with-sqlite --with-bzlib --with-zstd \
     --with-readline --with-freetype --with-freetype-includes=/usr/include/freetype2 --with-blas --with-lapack \
     --without-wxwidgets --without-opengl --without-fftw --without-cairo --without-pdal --without-postgres --without-mysql --without-odbc \
     > configure.log 2>&1 || { tail -20 configure.log; exit 1; }
  make -j"$(nproc)" > make.log 2>&1 || { tail -20 make.log; exit 1; }
  sudo make install > install.log 2>&1
  cd $HOME
fi
echo "   $(grass --version | head -1)"

echo "== r.avaflow 4.0G"
GB=$(grass --config path)
DL=$HOME/avaflow_download; SRC=$DL/r.avaflow.40G; ADDONS=$HOME/.grass8/addons
mkdir -p "$DL" "$ADDONS/bin" "$ADDONS/scripts"
[ -f "$DL/r.avaflow.40G.zip" ] || curl -sL -o "$DL/r.avaflow.40G.zip" https://www.landslidemodels.org/r.avaflow/software/r.avaflow.40G.zip
[ -d "$SRC" ] || unzip -q "$DL/r.avaflow.40G.zip" -d "$DL"
cc -O2 -w -DPACKAGE='"grassmods"' -I"$GB/include" $(gdal-config --cflags) "$SRC/r.avaflow.main/main.c" \
   -L"$GB/lib" -Wl,-rpath,"$GB/lib" -lgrass_gis -lgrass_raster -lgrass_segment -lm -o "$ADDONS/bin/r.avaflow.main"
for m in r.avaflow/r.avaflow.40G r.lakefill/r.lakefill r.scarp/r.scarp r.avaflow.mult/r.avaflow.mult r.avaflow.background/r.avaflow.background; do
  cp "$SRC/$m.py" "$ADDONS/scripts/$(basename $m)"; chmod +x "$ADDONS/scripts/$(basename $m)"
done
grass --tmp-project EPSG:6542 --exec r.avaflow.40G --help 2>&1 | head -2

echo "== python packages"
pip3 install -q --user numpy rasterio fiona shapely pyproj matplotlib

echo "== tippecanoe"
if ! command -v tippecanoe >/dev/null; then
  rm -rf $HOME/tippecanoe; git clone -q --depth 1 https://github.com/felt/tippecanoe.git $HOME/tippecanoe
  (cd $HOME/tippecanoe && make -j"$(nproc)" >/dev/null 2>&1 && sudo make install >/dev/null)
fi
echo "   $(tippecanoe --version 2>&1 | head -1)"

echo "== git and the repo"
cat > ~/.ssh/config <<EOF
Host github.com
  IdentityFile ~/.ssh/landslide-deploy-key
  IdentitiesOnly yes
  StrictHostKeyChecking accept-new
EOF
chmod 600 ~/.ssh/config
git config --global user.name "Dave Michelson"
git config --global user.email "dmichels@unca.edu"
[ -d "$DIR/.git" ] || git clone -q "$REPO" "$DIR"
(cd "$DIR" && git pull -q --rebase && echo "   $(git log --oneline -1)")
mkdir -p "$DIR/logs" "$DIR/avaflow_runs" "$DIR/inputs" "$DIR/outputs"
echo "== setup done"
