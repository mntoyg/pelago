// Camera targets for each drill level, and zoom.
import { DEG } from '../utils.js';
import { COUNTRIES } from '../data/spots.js';
import { selection, runtime, target } from '../state.js';
import { viewport } from './canvas.js';

// Camera position for the current selection: whole of Asia, a country, a province, or a single spot.
export function goalForSelection() {
  const w = Math.max(viewport.w, 520), s = Math.min(viewport.w, viewport.h);
  if (!selection.country) return { lo: 102, la: 12, R: s * 0.7 };
  const country = COUNTRIES[selection.country];
  if (selection.province == null) return { lo: country.center[0], la: country.center[1], R: w / (country.span * DEG) };
  const province = country.provinces[selection.province], n = province.spots.length;
  const mid = province.spots.reduce((a, q) => [a[0] + q.coord[0] / n, a[1] + q.coord[1] / n], [0, 0]);
  if (selection.spot == null) return { lo: mid[0], la: mid[1], R: w / (4.5 * DEG) };
  const spot = province.spots[selection.spot];
  return { lo: spot.coord[0], la: spot.coord[1], R: w / (2.6 * DEG) };
}

// Multiplies the zoom target by f (cancelling any fly-to animation), clamped to a sane range.
export function zoomBy(f) {
  runtime.anim = null;
  target.R = Math.min(Math.max(target.R * f, Math.min(viewport.w, viewport.h) * 0.5), 9e5);
}
