// Live sea data per spot (NOAA ERDDAP: SST, chlorophyll, depth) plus the local moon phase, combined into the
// FSI v1 score. This is the data-access seam: to move FSI to a backend, replace fetchSpotSignal() so it resolves
// the same { sst, sstT, chl, chlT, depth, moon } object (and still sets spot.fsi / spot.signal).
import { ERDDAP_BASE, FSI_WEIGHTS, FSI_TARGETS } from '../config.js';
import { sourceStatus } from './source-status.js';

// Rows of an ERDDAP .json table; throws on HTTP errors.
async function fetchRows(url) {
  const r = await fetch(url);
  if (!r.ok) throw 0;
  return (await r.json()).table.rows;
}

// Moon phase from the date: { ph: 0..1 through the cycle, age: days, ill: illuminated fraction }.
function moonPhase(d = new Date()) {
  const synodic = 29.530588853, k = (d.getTime() / 864e5 - 10962.76) / synodic, ph = ((k % 1) + 1) % 1;
  return { ph, age: ph * synodic, ill: (1 - Math.cos(2 * Math.PI * ph)) / 2 };
}

export function moonText() {
  const m = moonPhase();
  const name = m.ph < 0.0625 || m.ph > 0.9375 ? 'จันทร์ดับ'
    : m.ph < 0.4375 ? 'ข้างขึ้น ' + Math.max(1, Math.round(m.age)) + ' ค่ำ'
    : m.ph < 0.5625 ? 'เต็มดวง'
    : 'ข้างแรม ' + Math.max(1, Math.round(m.age - 14.77)) + ' ค่ำ';
  return name + ' · สว่าง ' + Math.round(m.ill * 100) + '% (โดยประมาณ)';
}

// FSI v1 (0-100) from an observation { sst, sstT, chl, chlT, depth, moon }. Each factor is scored 0..1 and weighted
// by how fresh its observation is. Returns null when there is no sea data at all.
function computeFsi(o) {
  const ageDays = t => t ? Math.max(0, (Date.now() - new Date(t)) / 864e5) : 9;
  const freshness = t => Math.exp(-Math.max(0, ageDays(t) - 1) / 3);
  const T = FSI_TARGETS;
  const score = {
    sst: o.sst != null ? Math.exp(-(((o.sst - T.sst) / T.sw) ** 2) / 2) : 0,
    chl: o.chl != null ? (o.chl > T.bloom ? 0 : Math.exp(-((Math.log10(o.chl) - T.lc) ** 2) / (2 * T.lw ** 2))) : 0,
    depth: o.depth != null ? Math.max(0, Math.min(1, Math.min(o.depth / 10, (200 - o.depth) / 120))) : 0,
    moon: 1 - o.moon.ill * 0.6,
    season: 0.5,
  };
  const confidence = {
    sst: o.sst != null ? freshness(o.sstT) : 0,
    chl: o.chl != null ? freshness(o.chlT) : 0,
    depth: o.depth != null ? 1 : 0,
    moon: 1,
    season: 1,
  };
  if (o.sst == null && o.chl == null && o.depth == null) return null;
  let num = 0, den = 0;
  for (const k in FSI_WEIGHTS) {
    num += FSI_WEIGHTS[k] * confidence[k] * score[k];
    den += FSI_WEIGHTS[k] * confidence[k];
  }
  return 100 * num / den;
}

// Starts (once per spot) the three NOAA requests for the spot's position and resolves the observation object.
// On success it overwrites spot.fsi and sets spot.signal. Each source reports its status in sourceStatus.
export function fetchSpotSignal(spot) {
  if (spot.signalPromise) return spot.signalPromise;
  const lat = spot.coord[1], lon = spot.coord[0], o = { moon: moonPhase() };
  spot.signalPromise = (async () => {
    try {
      const rows = await fetchRows(ERDDAP_BASE + `jplMURSST41.json?analysed_sst[(last)][(${lat})][(${lon})]`);
      if (rows[0][3] != null) { o.sst = rows[0][3]; o.sstT = rows[0][0]; }
      sourceStatus.sst = 1;
    } catch (e) { if (sourceStatus.sst !== 1) sourceStatus.sst = -1; }
    try {
      let rows;
      try {
        rows = await fetchRows(ERDDAP_BASE + `nesdisVHNchlaDaily.json?chlor_a[last-3:1:last][0:1:0][(${lat})][(${lon})]`);
      } catch (e) {
        // Some chlorophyll grids have no altitude axis: retry without it.
        rows = await fetchRows(ERDDAP_BASE + `nesdisVHNchlaDaily.json?chlor_a[last-3:1:last][(${lat})][(${lon})]`);
      }
      const latest = rows.filter(row => row[row.length - 1] != null).pop();   // newest cloud-free day
      if (latest) { o.chl = latest[latest.length - 1]; o.chlT = latest[0]; }
      sourceStatus.chl = 1;
    } catch (e) { if (sourceStatus.chl !== 1) sourceStatus.chl = -1; }
    try {
      const rows = await fetchRows(ERDDAP_BASE + `ETOPO_2022_v1_15s.json?z[(${lat})][(${lon})]`);
      if (rows[0][2] != null) o.depth = Math.max(0, -rows[0][2]);
      sourceStatus.depth = 1;
    } catch (e) { if (sourceStatus.depth !== 1) sourceStatus.depth = -1; }
    const fsi = computeFsi(o);
    if (fsi != null) { spot.fsi = Math.round(fsi); spot.signal = o; }
    return o;
  })();
  return spot.signalPromise;
}
