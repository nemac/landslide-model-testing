// Overture Maps buildings and roads, read straight from Overture's public PMTiles in the
// browser (HTTP range requests; nothing is downloaded up front). Two jobs:
//   1. find the newest release in the bucket, so no date is hard-coded
//   2. count the buildings and road segments that touch a run's deposit footprint, by
//      fetching the handful of z14 tiles around the slide and testing each feature
import { PMTiles } from "pmtiles";
import { VectorTile } from "@mapbox/vector-tile";
import Pbf from "pbf";
import * as turf from "@turf/turf";

export const OVERTURE_BUCKET = "https://overturemaps-extras-us-west-2.s3.us-west-2.amazonaws.com";
export const OVERTURE_FALLBACK_RELEASE = "2026-10-21.0";
const Z = 14;                        // Overture tiles stop at z14

export async function latestOvertureRelease(): Promise<string> {
  try {
    const xml = await (await fetch(`${OVERTURE_BUCKET}/?list-type=2&prefix=tiles/&delimiter=/`)).text();
    const rel = Array.from(xml.matchAll(/<Prefix>tiles\/([^<\/]+)\/<\/Prefix>/g)).map((m) => m[1]).sort();
    return rel.length ? rel[rel.length - 1] : OVERTURE_FALLBACK_RELEASE;
  } catch {
    return OVERTURE_FALLBACK_RELEASE;
  }
}

export const overtureUrl = (release: string, theme: "buildings" | "transportation") => `${OVERTURE_BUCKET}/tiles/${release}/${theme}.pmtiles`;

export interface Impacts {
  buildings: number;
  roads: number;
  roadsByClass: Record<string, number>;
  roadLengthM: number;
  footprintM2: number;
  tiles: number;
  buildingFeatures: GeoJSON.Feature[];   // the buildings counted, for drawing
  roadFeatures: GeoJSON.Feature[];       // the road segments counted, for drawing
}

function tileXY(lon: number, lat: number, z: number) {
  const n = 2 ** z;
  const x = Math.floor(((lon + 180) / 360) * n);
  const latR = (lat * Math.PI) / 180;
  const y = Math.floor(((1 - Math.log(Math.tan(latR) + 1 / Math.cos(latR)) / Math.PI) / 2) * n);
  return { x, y };
}

async function tileFeatures(pm: PMTiles, layer: string, z: number, x: number, y: number): Promise<GeoJSON.Feature[]> {
  const t = await pm.getZxy(z, x, y);
  if (!t) return [];
  const vt = new VectorTile(new Pbf(new Uint8Array(t.data)));
  const l = vt.layers[layer];
  if (!l) return [];
  const out: GeoJSON.Feature[] = [];
  for (let i = 0; i < l.length; i++) out.push(l.feature(i).toGeoJSON(x, y, z) as GeoJSON.Feature);
  return out;
}

/**
 * Buildings and roads touching the deposit of one run of one slide. Looks at the 3 x 3
 * block of z14 tiles around the release point (about 7 km across), which covers the box.
 */
export async function countImpacts(slidesUrl: string, release: string, lon: number, lat: number, run: string, fid: number): Promise<Impacts> {
  const slides = new PMTiles(slidesUrl);
  const bld = new PMTiles(overtureUrl(release, "buildings"));
  const trn = new PMTiles(overtureUrl(release, "transportation"));
  const { x, y } = tileXY(lon, lat, Z);
  const tiles: [number, number][] = [];
  for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) tiles.push([x + dx, y + dy]);

  // the footprint: this run's deposit polygons for this slide, from our own tiles
  const dep = (await Promise.all(tiles.map(([tx, ty]) => tileFeatures(slides, "deposit", Z, tx, ty)))).flat()
    .filter((f) => f.properties?.run === run && Number(f.properties?.source_fid) === fid);
  const empty: Impacts = { buildings: 0, roads: 0, roadsByClass: {}, roadLengthM: 0, footprintM2: 0, tiles: tiles.length, buildingFeatures: [], roadFeatures: [] };
  if (!dep.length) return empty;
  const footprintM2 = dep.reduce((a, f) => a + turf.area(f as any), 0);
  const depBoxes = dep.map((f) => turf.bbox(f as any));
  const touches = (g: GeoJSON.Feature) => {
    const b = turf.bbox(g as any);
    for (let i = 0; i < dep.length; i++) {
      const d = depBoxes[i];
      if (b[2] < d[0] || b[0] > d[2] || b[3] < d[1] || b[1] > d[3]) continue;
      if (turf.booleanIntersects(g as any, dep[i] as any)) return true;
    }
    return false;
  };

  // buildings, once each (tiles clip features at their edges, so the same id can appear twice)
  const seenB = new Set<string>();
  let buildings = 0;
  const buildingFeatures: GeoJSON.Feature[] = [];
  for (const f of (await Promise.all(tiles.map(([tx, ty]) => tileFeatures(bld, "building", Z, tx, ty)))).flat()) {
    const id = String(f.properties?.id ?? JSON.stringify(f.geometry));
    if (seenB.has(id)) continue;
    if (touches(f)) { seenB.add(id); buildings++; buildingFeatures.push(f); }
  }
  // road segments, once each, with the length of the part inside the footprint
  const seenR = new Set<string>();
  let roads = 0, roadLengthM = 0;
  const roadsByClass: Record<string, number> = {};
  const roadFeatures: GeoJSON.Feature[] = [];
  for (const f of (await Promise.all(tiles.map(([tx, ty]) => tileFeatures(trn, "segment", Z, tx, ty)))).flat()) {
    if (f.properties?.subtype && f.properties.subtype !== "road") continue;   // rail, water and such are not roads
    const id = String(f.properties?.id ?? JSON.stringify(f.geometry));
    if (seenR.has(id) || !touches(f)) continue;
    seenR.add(id); roads++; roadFeatures.push(f);
    const cls = String(f.properties?.class ?? "unknown");
    roadsByClass[cls] = (roadsByClass[cls] ?? 0) + 1;
    try {
      for (const d of dep) {
        const inside = turf.lineSplit(f as any, d as any);
        const pieces = inside.features.length ? inside.features : [f];
        for (const p of pieces) {
          const mid = turf.along(p as any, turf.length(p as any) / 2);
          if (turf.booleanPointInPolygon(mid, d as any)) roadLengthM += turf.length(p as any, { units: "meters" });
        }
      }
    } catch { /* odd geometry: count it, skip the length */ }
  }
  return { buildings, roads, roadsByClass, roadLengthM: Math.round(roadLengthM), footprintM2: Math.round(footprintM2), tiles: tiles.length, buildingFeatures, roadFeatures };
}
