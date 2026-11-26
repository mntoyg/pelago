// Raster tile layers (NASA GIBS + Esri) drawn onto the globe.
import { DEG } from '../utils.js';
import { ESRI_IMAGERY_TILE_URL, TILE_LAYERS } from '../config.js';
import { view, layers } from '../state.js';
import { ctx, viewport, GLOBE_CENTER_Y, FULL_CIRCLE } from './canvas.js';
import { project } from './projection.js';

const TILE_CACHE_LIMIT = 260;
const tileCache = new Map();   // key -> { im: HTMLImageElement, ok: loaded? }

const isoDate = ms => new Date(ms).toISOString().slice(0, 10);

// Date segment used by the daily layers: yesterday (UTC), so the swath is complete.
let imageryDate = isoDate(Date.now() - 864e5);

// Moves daily layers to yesterday's date and drops their cached tiles. Returns the date used.
export function refreshImageryDate() {
  imageryDate = isoDate(Date.now() - 864e5);
  for (const key of [...tileCache.keys()]) if (/^(liv|chl|sst)/.test(key)) tileCache.delete(key);
  return imageryDate;
}

// Returns the loaded image for a tile, or null while it is still loading (loading is started on first request).
function tile(layer, z, tx, ty) {
  const id = layer + z + '/' + tx + '/' + ty;
  let entry = tileCache.get(id);
  if (!entry) {
    const im = new Image();
    entry = { im, ok: 0 };
    im.onload = () => { entry.ok = 1; };
    // The base layer switches to Esri imagery past zoom 5.
    const template = layer === 'img' && z > 5 ? ESRI_IMAGERY_TILE_URL : TILE_LAYERS[layer].template;
    im.src = template.replace('{date}', imageryDate).replace('{z}', z).replace('{y}', ty).replace('{x}', tx);
    tileCache.set(id, entry);
    if (tileCache.size > TILE_CACHE_LIMIT) tileCache.delete(tileCache.keys().next().value);
  }
  return entry.ok ? entry.im : null;
}

// Draws every enabled raster layer. Each web-mercator tile is split into a G x G grid of small quads and each quad
// is drawn with an affine transform, which approximates the orthographic warp.
export function drawTiles() {
  if (view.R < 250) return;
  const W = viewport.w, H = viewport.h;
  for (const layer of ['img', 'liv', 'chl', 'sst']) {
    if (!layers[layer]) continue;
    const cfg = TILE_LAYERS[layer];
    let z = Math.round(Math.log2(2 * Math.PI * view.R / 256));
    z = Math.max(2, Math.min(layer === 'img' ? 16 : cfg.maxZoom, z));
    const G = z < 6 ? 8 : z < 9 ? 4 : 2, q = 256 / G;
    const n = 1 << z;
    const lat = Math.max(-80, Math.min(80, view.la));
    const cx = Math.floor((view.lo + 180) / 360 * n);
    const cy = Math.floor((1 - Math.log(Math.tan(Math.PI / 4 + lat * DEG / 2)) / Math.PI) / 2 * n);
    const span = Math.min(7, Math.ceil(Math.max(W, H) / (2 * Math.PI * view.R / n)) + 1);

    ctx.save();
    ctx.beginPath();
    ctx.arc(W / 2, H * GLOBE_CENTER_Y, view.R, 0, FULL_CIRCLE);
    ctx.clip();
    ctx.globalAlpha = cfg.alpha;
    ctx.globalCompositeOperation = layer === 'liv' ? 'lighten' : 'source-over';
    for (let dy = -span; dy <= span; dy++) {
      for (let dx = -span; dx <= span; dx++) {
        const ty = cy + dy, ux = cx + dx;
        if (ty < 0 || ty >= n) continue;
        const im = tile(layer, z, ((ux % n) + n) % n, ty);
        if (!im) continue;
        for (let i = 0; i < G; i++) {
          for (let j = 0; j < G; j++) {
            const lon = u => (ux + u) / n * 360 - 180;
            const latOf = v => Math.atan(Math.sinh(Math.PI * (1 - 2 * (ty + v) / n))) / DEG;
            const p00 = project(lon(i / G), latOf(j / G));
            const p10 = project(lon((i + 1) / G), latOf(j / G));
            const p01 = project(lon(i / G), latOf((j + 1) / G));
            if (p00[2] < 0.04 || p10[2] < 0.04 || p01[2] < 0.04) continue;
            ctx.save();
            ctx.transform((p10[0] - p00[0]) / q, (p10[1] - p00[1]) / q, (p01[0] - p00[0]) / q, (p01[1] - p00[1]) / q, p00[0], p00[1]);
            ctx.drawImage(im, i * q, j * q, q, q, 0, 0, q + 0.7, q + 0.7);  // +0.7 hides seams between quads
            ctx.restore();
          }
        }
      }
    }
    ctx.restore();
  }
}
