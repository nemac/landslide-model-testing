import { useEffect, useRef } from "react";
import maplibregl, { Map, MapMouseEvent } from "maplibre-gl";
import { Protocol } from "pmtiles";
import { ARRIVAL_BINS, BASEMAPS, BasemapKey, BUILDING_COLOR, DEPTH_BANDS, LayerId, ROAD_COLOR, Slide } from "./config";

const CLICKABLE = ["deposit-fill", "arrival-fill", "hydrograph-pt", "sources-fill", "points-pt"];
const RUN_LAYERS = ["deposit-fill", "arrival-fill", "deposit-3d", "arrival-3d", "hydrograph-pt"];
const DEPTH_STEP_M = 30;           // 3D height step per depth band: 30, 60, 90, 120, 150 m
const ARRIVAL_STEP_M = 40;         // 3D height step per arrival bin: 40, 80, 120 m
const TILT_PITCH = 60;

// Buttons for tilt and spin, next to the zoom and compass buttons.
class TiltSpinControl {
  private map: Map | null = null;
  private box: HTMLDivElement | null = null;
  onAdd(map: Map) {
    this.map = map;
    this.box = document.createElement("div");
    this.box.className = "maplibregl-ctrl maplibregl-ctrl-group";
    const mk = (title: string, text: string, fn: () => void) => {
      const b = document.createElement("button"); b.type = "button"; b.title = title; b.textContent = text;
      b.style.fontSize = "13px"; b.style.fontWeight = "600"; b.onclick = fn; this.box!.appendChild(b);
    };
    mk("Tilt the map (3D)", "3D", () => map.easeTo({ pitch: map.getPitch() > 0 ? 0 : TILT_PITCH, duration: 500 }));
    mk("Spin the map", "↻", () => map.easeTo({ bearing: map.getBearing() + 45, duration: 500 }));
    return this.box;
  }
  onRemove() { this.box?.remove(); this.map = null; }
}
const SOURCE_LAYERS = ["sources-fill", "sources-line", "points-pt"];

interface Props {
  run: string;
  fid: number | null;            // one slide, or null for all
  basemap: BasemapKey;
  visible: Record<LayerId, boolean>;
  slides: Slide[];
  version: string;               // data build stamp, so a new tile file is not served from the browser cache
  hits: { buildings: GeoJSON.FeatureCollection; roads: GeoJSON.FeatureCollection } | null;   // the Overture features the stats counted
  onPick: (fid: number) => void;
}

export default function MapView({ run, fid, basemap, visible, slides, version, hits, onPick }: Props) {
  const TILES = new URL(`data/landslides.pmtiles?v=${version}`, document.baseURI).href;
  const INVENTORY = new URL("data/nc_landslide_inventory.pmtiles", document.baseURI).href;
  const div = useRef<HTMLDivElement>(null);
  const map = useRef<Map | null>(null);
  const ready = useRef(false);
  const pick = useRef(onPick);
  pick.current = onPick;
  const latest = useRef({ run, fid, basemap, visible });
  latest.current = { run, fid, basemap, visible };

  // build the map once
  useEffect(() => {
    if (!div.current || map.current) return;
    const protocol = new Protocol();
    maplibregl.addProtocol("pmtiles", protocol.tile);
    const baseSources: Record<string, any> = {};
    const baseLayers: any[] = [];
    for (const k of Object.keys(BASEMAPS) as BasemapKey[]) {
      // maxzoom lets the map keep showing the basemap past the zoom its tiles stop at
      baseSources[k] = { type: "raster", tiles: [...BASEMAPS[k].tiles], tileSize: 256, attribution: BASEMAPS[k].attribution, maxzoom: BASEMAPS[k].maxzoom };
      baseLayers.push({ id: `base-${k}`, type: "raster", source: k, layout: { visibility: "none" } });
    }
    const m = new maplibregl.Map({
      container: div.current,
      style: {
        version: 8,
        sources: {
          ...baseSources,
          slides: { type: "vector", url: `pmtiles://${TILES}` },
          inventory: { type: "vector", url: `pmtiles://${INVENTORY}`, attribution: "NC Geological Survey landslide inventory" },
          "hit-buildings": { type: "geojson", data: { type: "FeatureCollection", features: [] }, attribution: "© Overture Maps Foundation" },
          "hit-roads": { type: "geojson", data: { type: "FeatureCollection", features: [] } },
          // elevation tiles for 3D terrain when the map is tilted (AWS Terrarium, open data)
          "terrain-dem": { type: "raster-dem", tiles: ["https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"], encoding: "terrarium", tileSize: 256, maxzoom: 15 },
        },
        layers: [
          ...baseLayers,
          { id: "inventory-fill", type: "fill", source: "inventory", "source-layer": "inventory", paint: { "fill-color": "#1f78b4", "fill-opacity": 0.35, "fill-outline-color": "#1f78b4" } },
          { id: "inventory-line", type: "line", source: "inventory", "source-layer": "inventory", paint: { "line-color": "#1f78b4", "line-width": 1 } },
          {
            id: "deposit-fill", type: "fill", source: "slides", "source-layer": "deposit",
            paint: {
              "fill-color": ["match", ["get", "band_m"], ...DEPTH_BANDS.flatMap((b) => [b.band, b.color]), "#54278f"] as any,
              "fill-outline-color": ["match", ["get", "band_m"], ...DEPTH_BANDS.flatMap((b) => [b.band, b.color]), "#54278f"] as any,
              "fill-opacity": 0.85,
            },
          },
          {
            id: "arrival-fill", type: "fill", source: "slides", "source-layer": "arrival",
            paint: {
              "fill-color": ["match", ["get", "arrival_min"], ...ARRIVAL_BINS.flatMap((b) => [b.bin, b.color]), "#a63603"] as any,
              "fill-outline-color": ["match", ["get", "arrival_min"], ...ARRIVAL_BINS.flatMap((b) => [b.bin, b.color]), "#a63603"] as any,
              "fill-opacity": 0.8,
            },
          },
          // 3D versions, shown when the map is tilted: height from depth (exaggerated) or arrival time
          {
            id: "deposit-3d", type: "fill-extrusion", source: "slides", "source-layer": "deposit", layout: { visibility: "none" },
            paint: {
              "fill-extrusion-color": ["match", ["get", "band_m"], ...DEPTH_BANDS.flatMap((b) => [b.band, b.color]), "#54278f"] as any,
              // a clear step per depth band rather than true depth, so every band reads as a terrace
              "fill-extrusion-height": ["match", ["get", "band_m"], ...DEPTH_BANDS.flatMap((b, i) => [b.band, (i + 1) * DEPTH_STEP_M]), DEPTH_STEP_M] as any,
              "fill-extrusion-opacity": 0.9,
            },
          },
          {
            id: "arrival-3d", type: "fill-extrusion", source: "slides", "source-layer": "arrival", layout: { visibility: "none" },
            paint: {
              "fill-extrusion-color": ["match", ["get", "arrival_min"], ...ARRIVAL_BINS.flatMap((b) => [b.bin, b.color]), "#a63603"] as any,
              "fill-extrusion-height": ["match", ["get", "arrival_min"], ...ARRIVAL_BINS.flatMap((b, i) => [b.bin, (i + 1) * ARRIVAL_STEP_M]), ARRIVAL_STEP_M] as any,
              "fill-extrusion-opacity": 0.9,
            },
          },
          // the Overture buildings and roads the stats counted, nothing else
          { id: "hit-buildings", type: "fill", source: "hit-buildings", paint: { "fill-color": BUILDING_COLOR, "fill-opacity": 0.95, "fill-outline-color": "#8c6d1f" } },
          { id: "hit-roads", type: "line", source: "hit-roads", paint: { "line-color": ROAD_COLOR, "line-width": ["interpolate", ["linear"], ["zoom"], 12, 2, 16, 5] } },
          { id: "sources-fill", type: "fill", source: "slides", "source-layer": "sources", paint: { "fill-color": "#1b9e77", "fill-opacity": 0.25 } },
          { id: "sources-line", type: "line", source: "slides", "source-layer": "sources", paint: { "line-color": "#1b9e77", "line-width": 1.5 } },
          { id: "points-pt", type: "circle", source: "slides", "source-layer": "points", paint: { "circle-radius": 5, "circle-color": "#1b9e77", "circle-stroke-color": "#fff", "circle-stroke-width": 1.5 } },
          { id: "hydrograph-pt", type: "circle", source: "slides", "source-layer": "hydrograph", paint: { "circle-radius": 7, "circle-color": "#2b6f8b", "circle-stroke-color": "#fff", "circle-stroke-width": 2 } },
        ],
      },
      center: [-82.5, 35.6],
      zoom: 9,
    });
    m.addControl(new maplibregl.NavigationControl({ visualizePitch: true, showCompass: true, showZoom: true }), "top-right");
    m.addControl(new TiltSpinControl() as any, "top-right");
    // tilted: 3D terrain on and the extruded layers; flat: plain fills
    const tilted = () => {
      const on = m.getPitch() > 0;
      m.setTerrain(on ? { source: "terrain-dem", exaggeration: 1.3 } : null as any);
      apply(m);
    };
    m.on("pitchend", tilted);
    m.addControl(new maplibregl.ScaleControl({ unit: "metric" }));
    m.on("load", () => {
      ready.current = true;
      for (const id of CLICKABLE) {
        m.on("mouseenter", id, () => (m.getCanvas().style.cursor = "pointer"));
        m.on("mouseleave", id, () => (m.getCanvas().style.cursor = ""));
      }
      m.on("click", (e: MapMouseEvent) => {
        const hits = m.queryRenderedFeatures(e.point, { layers: CLICKABLE.filter((l) => m.getLayer(l)) });
        const f = hits.find((h) => h.properties && h.properties.source_fid != null)?.properties?.source_fid;
        if (f != null) pick.current(Number(f));
      });
      apply(m);
      zoom(m);
    });
    map.current = m;
    return () => { m.remove(); map.current = null; ready.current = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // the counted features, whenever the stats change
  useEffect(() => {
    const m = map.current;
    if (!m || !ready.current) return;
    const empty = { type: "FeatureCollection", features: [] } as GeoJSON.FeatureCollection;
    (m.getSource("hit-buildings") as any)?.setData(hits?.buildings ?? empty);
    (m.getSource("hit-roads") as any)?.setData(hits?.roads ?? empty);
  }, [hits]);

  // zoom to the chosen slide, or to all of them
  const zoom = (m: Map) => {
    if (!slides.length) return;
    const s = fid != null ? slides.find((x) => x.fid === fid) : null;
    if (s) {
      m.flyTo({ center: [s.lon, s.lat], zoom: 14.5, duration: 600 });
    } else {
      const b = new maplibregl.LngLatBounds();
      slides.forEach((x) => b.extend([x.lon, x.lat]));
      m.fitBounds(b, { padding: 60, maxZoom: 13, duration: 600 });
    }
  };
  useEffect(() => {
    if (map.current && ready.current) zoom(map.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fid, slides]);

  // run and slide filters, basemap, visibility
  const apply = (m: Map) => {
    const { run, fid, basemap, visible } = latest.current;
    const byRun: any = ["==", ["get", "run"], run];
    const byFid: any = fid != null ? ["==", ["get", "source_fid"], fid] : null;
    for (const id of RUN_LAYERS) m.setFilter(id, byFid ? ["all", byRun, byFid] : byRun);
    for (const id of SOURCE_LAYERS) m.setFilter(id, byFid);
    for (const k of Object.keys(BASEMAPS) as BasemapKey[]) m.setLayoutProperty(`base-${k}`, "visibility", k === basemap ? "visible" : "none");
    const show = (ids: string[], on: boolean) => ids.forEach((id) => m.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
    const on3d = m.getPitch() > 0;
    show(["deposit-fill"], visible.deposit && !on3d);
    show(["deposit-3d"], visible.deposit && on3d);
    show(["arrival-fill"], visible.arrival && !on3d);
    show(["arrival-3d"], visible.arrival && on3d);
    show(["hydrograph-pt"], visible.hydrograph);
    show(["sources-fill", "sources-line"], visible.sources);
    show(["points-pt"], visible.points);
    show(["inventory-fill", "inventory-line"], visible.inventory);
    show(["hit-buildings"], visible.buildings);
    show(["hit-roads"], visible.roads);
  };
  useEffect(() => {
    if (map.current && ready.current) apply(map.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [run, fid, basemap, visible]);

  return <div ref={div} style={{ position: "absolute", inset: 0 }} />;
}
