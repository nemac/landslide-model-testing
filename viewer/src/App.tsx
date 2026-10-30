import { useEffect, useMemo, useState } from "react";
import {
  Box, Checkbox, Divider, Drawer, FormControl, FormControlLabel, IconButton, InputLabel, Link, MenuItem,
  Radio, RadioGroup, Select, Stack, Typography,
} from "@mui/material";
import MapView from "./MapView";
import { CompareCharts, ReviewCharts, SlideCharts } from "./Charts";
import { Impacts, countImpacts, latestOvertureRelease } from "./overture";
import { ARRIVAL_BINS, BASEMAPS, BasemapKey, DEPTH_BANDS, Index, LAYERS, LayerId, describeRun } from "./config";

const LEFT = 320;
const RIGHT = 560;
const ALL = "all";
const DEFAULT_FID = 1;
// blank charts for a run that has not been made yet
const EMPTY = { volumes: [], profile: [], bands: ["1-5 cm", "5-20 cm", "20-50 cm", "50-100 cm", ">100 cm"].map((label) => ({ label, area_m2: 0 })), storm: null };

export default function App() {
  const [index, setIndex] = useState<Index | null>(null);
  const [stopSlope, setStopSlope] = useState("15");
  const [storm, setStorm] = useState("none");
  const [slideSel, setSlideSel] = useState<string>(String(DEFAULT_FID));   // a fid as text, or "all"
  const [basemap, setBasemap] = useState<BasemapKey>("darkgray");
  const [visible, setVisible] = useState<Record<LayerId, boolean>>({ deposit: true, arrival: false, hydrograph: true, sources: true, points: true, inventory: true, buildings: true, roads: true });
  const [picked, setPicked] = useState<number | null>(DEFAULT_FID);   // charts open from the start
  const [chartData, setChartData] = useState<Record<string, SlideCharts>>({});
  const [release, setRelease] = useState<string | null>(null);
  const [impacts, setImpacts] = useState<Impacts | "counting" | null>(null);

  useEffect(() => {
    fetch(new URL(`data/index.json?t=${Date.now()}`, document.baseURI).href, { cache: "no-store" })
      .then((r) => r.json())
      .then((ix: Index) => {
        setIndex(ix);
        if (!ix.slides.some((s) => s.fid === DEFAULT_FID)) setSlideSel(ALL);
      });
    latestOvertureRelease().then(setRelease);
    fetch(new URL(`data/charts.json?t=${Date.now()}`, document.baseURI).href, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : {}))
      .then(setChartData)
      .catch(() => setChartData({}));
  }, []);

  const fid = slideSel === ALL ? null : Number(slideSel);
  // the choices on offer: the whole matrix when the index lists it, else whatever has results
  const stopSlopes = useMemo(() => index?.stop_slopes?.length
    ? index.stop_slopes.map(String)
    : Array.from(new Set((index?.runs ?? []).map((r) => r.match(/stopslope(\d+)/)?.[1]).filter(Boolean) as string[])).sort((a, b) => +a - +b), [index]);
  const storms = useMemo(() => ["none", ...(index?.storms_in?.length
    ? index.storms_in.map(String)
    : Array.from(new Set((index?.runs ?? []).map((r) => r.match(/storm(\d+)in/)?.[1]).filter(Boolean) as string[])).sort((a, b) => +a - +b))], [index]);
  const run = `stopslope${stopSlope}_soilsat_entrain${storm === "none" ? "" : `_storm${storm}in`}`;
  const runExists = !!index?.runs.includes(run);
  const slide = useMemo(() => index?.slides.find((s) => s.fid === picked) ?? null, [index, picked]);
  const row = useMemo(() => index?.summary.find((r) => r.slide_id === slide?.id && r.run === run) ?? null, [index, slide, run]);

  // buildings and roads touched by the chosen run of the chosen slide, from Overture's tiles
  useEffect(() => {
    if (!index || !release || fid == null || !runExists) { setImpacts(null); return; }
    const s = index.slides.find((x) => x.fid === fid);
    if (!s) { setImpacts(null); return; }
    let live = true;
    setImpacts("counting");
    const tiles = new URL(`data/landslides.pmtiles?v=${index.built ?? ""}`, document.baseURI).href;
    countImpacts(tiles, release, s.lon, s.lat, run, fid).then((r) => { if (live) setImpacts(r); }).catch(() => { if (live) setImpacts(null); });
    return () => { live = false; };
  }, [index, release, fid, run, runExists]);

  // the charts follow the run chosen on the left; the comparison of every run sits below
  const sc = slide ? chartData[slide.id] : undefined;
  const runData = sc?.runs[run];

  return (
    <Box sx={{ display: "flex", height: "100vh" }}>
      <Drawer variant="permanent" sx={{ width: LEFT, flexShrink: 0, "& .MuiDrawer-paper": { width: LEFT, p: 2, boxSizing: "border-box" } }}>
        <Typography variant="h6" gutterBottom>Landslide runout</Typography>
        <Typography variant="body2" color="text.secondary" gutterBottom>
          r.avaflow runs for the western NC source areas. Click a deposit, point or source for its graphs.
        </Typography>

        <FormControl fullWidth size="small" sx={{ mt: 2 }}>
          <InputLabel>Landslide</InputLabel>
          <Select label="Landslide" value={slideSel} onChange={(e) => { setSlideSel(e.target.value); if (e.target.value !== ALL) setPicked(Number(e.target.value)); }}>
            <MenuItem value={ALL}>All landslides</MenuItem>
            {index?.slides.map((s) => <MenuItem key={s.fid} value={String(s.fid)}>Landslide {s.fid} ({s.id})</MenuItem>)}
          </Select>
        </FormControl>

        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle2">Model run</Typography>
        <Typography variant="caption" color="text.secondary">Stop slope</Typography>
        <RadioGroup row value={stopSlope} onChange={(e) => setStopSlope(e.target.value)}>
          {stopSlopes.map((s) => <FormControlLabel key={s} value={s} control={<Radio size="small" />} label={<Typography variant="body2">{s}°</Typography>} />)}
        </RadioGroup>
        <Typography variant="caption" color="text.secondary">Soil</Typography>
        <RadioGroup row value="sat">
          <FormControlLabel value="sat" control={<Radio size="small" />} label={<Typography variant="body2">saturated</Typography>} />
        </RadioGroup>
        <Typography variant="caption" color="text.secondary">Entrainment</Typography>
        <RadioGroup row value="on">
          <FormControlLabel value="on" control={<Radio size="small" />} label={<Typography variant="body2">on</Typography>} />
        </RadioGroup>
        <Typography variant="caption" color="text.secondary">Rainfall in 24 hours</Typography>
        <RadioGroup row value={storm} onChange={(e) => setStorm(e.target.value)}>
          {storms.map((s) => <FormControlLabel key={s} value={s} control={<Radio size="small" />} label={<Typography variant="body2">{s === "none" ? "none" : `${s} in`}</Typography>} />)}
        </RadioGroup>
        <Typography variant="caption" color={runExists ? "text.secondary" : "error"}>{runExists ? run : `${run}: not run yet`}</Typography>
        <Typography variant="body2" sx={{ mt: 1 }}>
          <Link href="https://github.com/nemac/landslide-model-testing#readme" target="_blank" rel="noopener">Methodology</Link>
        </Typography>

        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle2">Layers</Typography>
        <Stack>
          {LAYERS.map((l) => (
            <FormControlLabel key={l.id} control={<Checkbox size="small" checked={visible[l.id]} onChange={(e) => setVisible({ ...visible, [l.id]: e.target.checked })} />} label={<Typography variant="body2">{l.label}</Typography>} />
          ))}
        </Stack>

        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle2">Basemap</Typography>
        <RadioGroup value={basemap} onChange={(e) => setBasemap(e.target.value as BasemapKey)}>
          {(Object.keys(BASEMAPS) as BasemapKey[]).map((k) => (
            <FormControlLabel key={k} value={k} control={<Radio size="small" />} label={<Typography variant="body2">{BASEMAPS[k].label}</Typography>} />
          ))}
        </RadioGroup>

        <Divider sx={{ my: 2 }} />
        <Typography variant="subtitle2" gutterBottom>Peak depth</Typography>
        {DEPTH_BANDS.map((b) => <Swatch key={b.band} color={b.color} label={b.label} />)}
        <Typography variant="subtitle2" sx={{ mt: 1.5 }} gutterBottom>Arrival time</Typography>
        {ARRIVAL_BINS.map((b) => <Swatch key={b.bin} color={b.color} label={b.label} />)}
      </Drawer>

      <Box sx={{ position: "relative", flex: 1 }}>
        {index && <MapView run={run} fid={fid} basemap={basemap} visible={visible} slides={index.slides} version={String(index.built ?? "")} hits={typeof impacts === "object" && impacts ? { buildings: { type: "FeatureCollection", features: impacts.buildingFeatures }, roads: { type: "FeatureCollection", features: impacts.roadFeatures } } : null} onPick={setPicked} />}
        {/* bottom panel: what the chosen run touches */}
        <Box sx={{ position: "absolute", left: 12, right: 12, bottom: 44, bgcolor: "rgba(250,250,250,0.95)", borderRadius: 1.5, p: 2, boxShadow: 3 }}>
          {fid == null ? (
            <Typography variant="body2" color="text.secondary">Pick one landslide to count the buildings and roads its deposit touches.</Typography>
          ) : impacts === "counting" || impacts === null ? (
            <Typography variant="body2" color="text.secondary">{impacts === "counting" ? "Counting buildings and roads in the deposit…" : runExists ? "Counts unavailable." : "Not run yet."}</Typography>
          ) : (
            <Stack direction="row" spacing={2} alignItems="stretch" flexWrap="wrap" useFlexGap>
              <Stat label="buildings touched" value={impacts.buildings} />
              <Stat label="road segments touched" value={impacts.roads} sub={Object.entries(impacts.roadsByClass).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${v} ${k.replace(/_/g, " ")}`)} />
              <Stat label="road length in the deposit" value={`${impacts.roadLengthM.toLocaleString()} m`} />
              <Stat label="deposit footprint" value={`${impacts.footprintM2.toLocaleString()} m²`} />
            </Stack>
          )}
          <Typography variant="caption" color="text.secondary" sx={{ display: "block", mt: 0.5 }}>
            Buildings and roads: Overture Maps Foundation, release {release ? release.slice(0, 10) : "…"}
          </Typography>
        </Box>
      </Box>

      <Box sx={{ width: slide ? RIGHT : 0, flexShrink: 0, p: slide ? 2 : 0, boxSizing: "border-box", overflowY: "auto", borderLeft: slide ? "1px solid #ddd" : "none", bgcolor: "background.paper" }}>
        {slide && (
          <>
            <Stack direction="row" alignItems="center" justifyContent="space-between">
              <Typography variant="h6">Landslide {slide.fid} ({slide.id})</Typography>
              <IconButton size="small" onClick={() => setPicked(null)} aria-label="close">✕</IconButton>
            </Stack>
            {slide.soil?.soil && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                Soil: {slide.soil.soil} {slide.soil.texture_class}, pile angle {slide.soil.pile_angle_deg}°, saturated water share {slide.soil.water_share}, soil depth {slide.soil.soil_depth_cm} cm
              </Typography>
            )}
            {row && (
              <Typography variant="body2" sx={{ mt: 1 }}>
                {describeRun(run)}: ground covered {Number(row.deposit_area_m2).toLocaleString()} m², farthest {Number(row.deposit_farthest_m).toLocaleString()} m,
                released {Number(row.released_m3).toLocaleString()} m³, entrained {Number(row.entrained_m3).toLocaleString()} m³, growth {row.growth}×
                {Number(row.storm_water_m3) > 0 ? `, storm water ${Number(row.storm_water_m3).toLocaleString()} m³` : ""}
              </Typography>
            )}
            <Typography variant="subtitle1" sx={{ mt: 2 }}>{describeRun(run)}{runData ? "" : " — not run yet"}</Typography>
            <ReviewCharts data={runData ?? EMPTY} released={sc?.released_m3 ?? 0} />
            <Divider sx={{ my: 3 }} />
            <Typography variant="subtitle1">All runs compared{sc && Object.keys(sc.runs).length ? "" : " — nothing run yet"}</Typography>
            <CompareCharts runs={sc?.runs ?? {}} />
          </>
        )}
      </Box>
    </Box>
  );
}

function Stat({ label, value, sub }: { label: string; value: number | string; sub?: string[] }) {
  return (
    <Stack direction="row" spacing={1.5} alignItems="flex-end" sx={{ border: "1px solid #ddd", borderRadius: 1.5, px: 2, py: 1.25, bgcolor: "#fff", minWidth: 170 }}>
      <Box>
        <Typography sx={{ fontSize: 60, lineHeight: 1, fontWeight: 800 }}>{typeof value === "number" ? value.toLocaleString() : value}</Typography>
        <Typography variant="caption" color="text.secondary">{label}</Typography>
      </Box>
      {sub && sub.length > 0 && (
        <Box sx={{ pb: 2.5 }}>
          {sub.map((line) => <Typography key={line} variant="caption" color="text.secondary" sx={{ display: "block", lineHeight: 1.35 }}>{line}</Typography>)}
        </Box>
      )}
    </Stack>
  );
}

function Swatch({ color, label }: { color: string; label: string }) {
  return (
    <Stack direction="row" spacing={1} alignItems="center">
      <Box sx={{ width: 18, height: 14, bgcolor: color, border: "1px solid #999" }} />
      <Typography variant="caption">{label}</Typography>
    </Stack>
  );
}

