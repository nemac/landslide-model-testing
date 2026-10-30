// Colours and labels shared by the map and the legend.
// ColorBrewer Purples (5 classes) for peak depth, darker = deeper.
export const DEPTH_BANDS: { band: string; label: string; color: string }[] = [
  { band: "0.01-0.05", label: "1–5 cm", color: "#f2f0f7" },
  { band: "0.05-0.2", label: "5–20 cm", color: "#cbc9e2" },
  { band: "0.2-0.5", label: "20–50 cm", color: "#9e9ac8" },
  { band: "0.5-1", label: "50–100 cm", color: "#756bb1" },
  { band: ">1", label: "over 1 m", color: "#54278f" },
];

// ColorBrewer Oranges (3 classes) for arrival time, darker = later.
export const ARRIVAL_BINS: { bin: string; label: string; color: string }[] = [
  { bin: "0-5", label: "0–5 min", color: "#fee6ce" },
  { bin: "5-10", label: "5–10 min", color: "#fdae6b" },
  { bin: "10-15", label: "10–15 min", color: "#e6550d" },
];

export const BASEMAPS = {
  darkgray: {
    label: "Esri dark gray",
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Esri, HERE, Garmin, © OpenStreetMap contributors, and the GIS user community",
    maxzoom: 16,
  },
  topo: {
    label: "USGS topo",
    tiles: ["https://basemap.nationalmap.gov/arcgis/rest/services/USGSTopo/MapServer/tile/{z}/{y}/{x}"],
    attribution: "USGS The National Map",
    maxzoom: 16,
  },
  hillshade: {
    label: "Esri hillshade",
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/Elevation/World_Hillshade/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Esri, USGS, NASA, NGA",
    maxzoom: 16,
  },
  imagery: {
    label: "Esri imagery",
    tiles: ["https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"],
    attribution: "Esri, Maxar, Earthstar Geographics, and the GIS User Community",
    maxzoom: 19,
  },
} as const;
export type BasemapKey = keyof typeof BASEMAPS;

// Map layers the user can switch on and off, in panel order.
export const LAYERS = [
  { id: "deposit", label: "Deposit, by peak depth" },
  { id: "arrival", label: "Arrival time" },
  { id: "hydrograph", label: "Storm inflow point" },
  { id: "sources", label: "Source areas" },
  { id: "points", label: "Release points" },
  { id: "inventory", label: "NC landslide inventory (NCGS)" },
] as const;
export type LayerId = (typeof LAYERS)[number]["id"];

export interface Slide {
  fid: number;
  id: string;
  lon: number;
  lat: number;
  soil: Record<string, string>;
}
export interface Index {
  built?: number;                 // when the data was built; used to defeat browser caching of the tiles
  slides: Slide[];
  runs: string[];                 // runs that have results
  stop_slopes?: number[];         // the full matrix, run or not
  storms_in?: number[];
  summary: Record<string, string>[];
}

// Plain-words description of a run name, e.g. stopslope15_soilsat_entrain_storm5in
export function describeRun(run: string): string {
  const parts: string[] = [];
  const m = run.match(/stopslope(\d+)/);
  if (m) parts.push(`stop slope ${m[1]}°`);
  if (run.includes("soilsat")) parts.push("saturated soil");
  if (run.includes("_dry")) parts.push("dry");
  const w = run.match(/water(\d+)/);
  if (w) parts.push(`water ${w[1]} %`);
  if (run.includes("entrain")) parts.push("entrainment");
  const s = run.match(/storm(\d+)in/);
  if (s) parts.push(`${s[1]} in storm`);
  return parts.join(", ") || run;
}
