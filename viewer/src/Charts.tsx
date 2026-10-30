// The four review panels, drawn from charts.json, stacked vertically. Same colours as
// the PNG figures made by avaflow_plots.py.
import { Box, Typography } from "@mui/material";
import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, LabelList, Legend, Line, LineChart,
  ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { describeRun } from "./config";

export interface RunData {
  volumes: { t_min: number; ground: number | null; water: number | null; total: number | null }[];
  profile: { dist_m: number; peak_m: number | null; first_s: number | null }[];
  bands: { label: string; area_m2: number }[];
  storm: { inflow_m3s: number; storm_in: number; catchment_m2?: number; peak_rain_in_per_h?: number } | null;
}
export interface SlideCharts { fid: number; released_m3: number; runs: Record<string, RunData> }

const GROUND = "#8b5a2b", WATER = "#2b6f8b", DEPTH = "#8b3a3a", GREY = "#888";
const PALETTE = ["#440154", "#31688e", "#35b779", "#fde725", "#e6550d", "#8b3a3a"];
const H = 230;

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle2" gutterBottom>{title}</Typography>
      <ResponsiveContainer width="100%" height={H}>{children as any}</ResponsiveContainer>
    </Box>
  );
}

const fmt = (v: any) => (typeof v === "number" ? v.toLocaleString(undefined, { maximumFractionDigits: 2 }) : v);

export function ReviewCharts({ data, released }: { data: RunData; released: number }) {
  const vols = data.volumes.map((v) => ({ ...v, storm: data.storm ? +(data.storm.inflow_m3s * v.t_min * 60).toFixed(1) : undefined }));
  // the storm hydrograph fed in at the release point: a steady inflow for the whole run
  const q = data.storm?.inflow_m3s ?? 0;
  const hydro = data.volumes.map((v) => ({ t_min: v.t_min, inflow: q, cumulative: +(q * v.t_min * 60).toFixed(1) }));
  return (
    <>
      {(
        <Panel title={data.storm
          ? `Storm hydrograph at the release point: ${data.storm.storm_in} in / 24 h` +
            (data.storm.catchment_m2 ? `, ${Math.round(data.storm.catchment_m2 / 100) / 100} ha drains to the point` : "") +
            (data.storm.peak_rain_in_per_h ? `, peak hour ${data.storm.peak_rain_in_per_h} in/h` : "")
          : "Storm hydrograph at the release point: no storm in this run"}>
          <LineChart data={hydro} margin={{ top: 5, right: 50, left: 0, bottom: 5 }}>
            <CartesianGrid strokeOpacity={0.3} />
            <XAxis dataKey="t_min" type="number" label={{ value: "minutes after release", position: "insideBottom", offset: -2, fontSize: 11 }} tick={{ fontSize: 11 }} />
            <YAxis yAxisId="q" tick={{ fontSize: 11 }} width={55} label={{ value: "m³/s", angle: -90, position: "insideLeft", fontSize: 11 }} />
            <YAxis yAxisId="v" orientation="right" tick={{ fontSize: 11 }} tickFormatter={fmt} width={55} label={{ value: "m³", angle: 90, position: "insideRight", fontSize: 11 }} />
            <Tooltip formatter={fmt} labelFormatter={(l) => `${l} min`} />
            <Legend wrapperStyle={{ fontSize: 11 }} />
            <Line yAxisId="q" type="stepAfter" dataKey="inflow" name="runoff flowing in, m³/s" stroke={WATER} strokeWidth={2} dot={false} isAnimationActive={false} />
            <Line yAxisId="v" type="monotone" dataKey="cumulative" name="water added so far, m³" stroke={WATER} strokeWidth={1} strokeDasharray="4 3" dot={false} isAnimationActive={false} />
          </LineChart>
        </Panel>
      )}
      <Panel title="Material in motion, m³">
        <LineChart data={vols} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeOpacity={0.3} />
          <XAxis dataKey="t_min" type="number" label={{ value: "minutes after release", position: "insideBottom", offset: -2, fontSize: 11 }} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={fmt} width={55} />
          <Tooltip formatter={fmt} labelFormatter={(l) => `${l} min`} />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <ReferenceLine y={released} stroke={GREY} strokeDasharray="2 4" label={{ value: `released ${fmt(released)}`, fontSize: 10, fill: GREY, position: "insideTopLeft" }} />
          <Line type="monotone" dataKey="ground" name="ground in motion" stroke={GROUND} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="water" name="water in motion" stroke={WATER} strokeWidth={2} dot={false} isAnimationActive={false} />
          <Line type="monotone" dataKey="total" name="total" stroke="#000" strokeWidth={1} strokeDasharray="5 4" dot={false} isAnimationActive={false} />
          {data.storm && <Line type="monotone" dataKey="storm" name={`storm runoff in, ${data.storm.inflow_m3s} m³/s`} stroke={WATER} strokeWidth={1} strokeDasharray="2 3" dot={false} isAnimationActive={false} />}
        </LineChart>
      </Panel>

      <Panel title="Peak depth down the valley, m">
        <AreaChart data={data.profile} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeOpacity={0.3} />
          <XAxis dataKey="dist_m" type="number" label={{ value: "metres down the valley from the release point", position: "insideBottom", offset: -2, fontSize: 11 }} tick={{ fontSize: 11 }} />
          <YAxis domain={[0, "auto"]} tick={{ fontSize: 11 }} width={55} />
          <Tooltip formatter={fmt} labelFormatter={(l) => `${l} m`} />
          <Area type="monotone" dataKey="peak_m" name="peak depth m" stroke={DEPTH} fill={DEPTH} fillOpacity={0.15} strokeWidth={2} isAnimationActive={false} connectNulls />
        </AreaChart>
      </Panel>

      <Panel title="Arrival time down the valley, seconds">
        <LineChart data={data.profile} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeOpacity={0.3} />
          <XAxis dataKey="dist_m" type="number" label={{ value: "metres down the valley from the release point", position: "insideBottom", offset: -2, fontSize: 11 }} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={55} />
          <Tooltip formatter={fmt} labelFormatter={(l) => `${l} m`} />
          <Line type="monotone" dataKey="first_s" name="first arrival s" stroke={WATER} strokeWidth={2} dot={{ r: 2 }} isAnimationActive={false} connectNulls />
        </LineChart>
      </Panel>

      <Panel title="Ground covered, by how deep the material got, m²">
        <BarChart data={data.bands} margin={{ top: 18, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeOpacity={0.3} vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} tickFormatter={fmt} width={60} />
          <Tooltip formatter={fmt} />
          <Bar dataKey="area_m2" name="m²" fill={GROUND} isAnimationActive={false}>
            <LabelList dataKey="area_m2" position="top" formatter={fmt} style={{ fontSize: 10 }} />
          </Bar>
        </BarChart>
      </Panel>
    </>
  );
}

// Every run of the slide on the same axes: peak depth and arrival.
export function CompareCharts({ runs }: { runs: Record<string, RunData> }) {
  const names = Object.keys(runs);
  // merge the profiles on distance so recharts can draw one line per run
  const dists = Array.from(new Set(names.flatMap((n) => runs[n].profile.map((p) => p.dist_m)))).sort((a, b) => a - b);
  const rows = dists.map((d) => {
    const row: Record<string, number | null> = { dist_m: d };
    names.forEach((n) => {
      const p = runs[n].profile.find((x) => x.dist_m === d);
      row[`${n}__peak`] = p?.peak_m ?? null;
      row[`${n}__first`] = p?.first_s ?? null;
    });
    return row;
  });
  return (
    <>
      <Panel title="Peak depth, m">
        <LineChart data={rows} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeOpacity={0.3} />
          <XAxis dataKey="dist_m" type="number" label={{ value: "metres down the valley", position: "insideBottom", offset: -2, fontSize: 11 }} tick={{ fontSize: 11 }} />
          <YAxis domain={[0, "auto"]} tick={{ fontSize: 11 }} width={55} />
          <Tooltip formatter={fmt} labelFormatter={(l) => `${l} m`} />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          {names.map((n, i) => <Line key={n} type="monotone" dataKey={`${n}__peak`} name={describeRun(n)} stroke={PALETTE[i % PALETTE.length]} strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls />)}
        </LineChart>
      </Panel>
      <Panel title="Arrival time, seconds">
        <LineChart data={rows} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <CartesianGrid strokeOpacity={0.3} />
          <XAxis dataKey="dist_m" type="number" label={{ value: "metres down the valley", position: "insideBottom", offset: -2, fontSize: 11 }} tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} width={55} />
          <Tooltip formatter={fmt} labelFormatter={(l) => `${l} m`} />
          <Legend wrapperStyle={{ fontSize: 10 }} />
          {names.map((n, i) => <Line key={n} type="monotone" dataKey={`${n}__first`} name={describeRun(n)} stroke={PALETTE[i % PALETTE.length]} strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls />)}
        </LineChart>
      </Panel>
    </>
  );
}
