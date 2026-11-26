// Orthographic globe projection and horizon-clipped polygon drawing.
import { DEG } from '../utils.js';
import { view } from '../state.js';
import { ctx, viewport, GLOBE_CENTER_Y } from './canvas.js';

// Project lon/lat (degrees) to canvas px. Returns [x, y, facing]; facing > 0 means the point is on the visible
// hemisphere. Points on the far side are pushed onto the globe's edge.
export function project(lon, lat) {
  const l = (lon - view.lo) * DEG, p = lat * DEG, p0 = view.la * DEG;
  const facing = Math.sin(p0) * Math.sin(p) + Math.cos(p0) * Math.cos(p) * Math.cos(l);
  let X = view.R * Math.cos(p) * Math.sin(l);
  let Y = view.R * (Math.cos(p0) * Math.sin(p) - Math.sin(p0) * Math.cos(p) * Math.cos(l));
  if (facing < 0) {
    const m = Math.hypot(X, Y) || 1;
    X = X / m * view.R;
    Y = Y / m * view.R;
  }
  return [viewport.w / 2 + X, viewport.h * GLOBE_CENTER_Y - Y, facing];
}

// Builds a canvas path for a lon/lat polygon, clipped to the visible hemisphere (the clipped edge follows the
// globe's rim). Returns false when nothing is visible, in which case the path is empty.
export function tracePolygon(points) {
  const p0 = view.la * DEG, s0 = Math.sin(p0), c0 = Math.cos(p0), R = view.R;
  const cx = viewport.w / 2, cy = viewport.h * GLOBE_CENTER_Y;
  // Unit-sphere coordinates [x, y, depth]; depth >= 0 is the visible side.
  const v = points.map(q => {
    const l = (q[0] - view.lo) * DEG, p = q[1] * DEG, cl = Math.cos(p), cL = Math.cos(l);
    return [cl * Math.sin(l), c0 * Math.sin(p) - s0 * cl * cL, s0 * Math.sin(p) + c0 * cl * cL];
  });
  const out = [];
  let exitAngle = null, firstEntryAngle = null;

  // Point where the edge a->b crosses the horizon, normalised onto the rim.
  const crossing = (a, b) => {
    const t = a[2] / (a[2] - b[2]);
    const q = [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t];
    const m = Math.hypot(q[0], q[1]) || 1;
    return [q[0] / m, q[1] / m, 0];
  };
  // Adds points along the rim from angle a1 to a2 (shortest way round).
  const rimArc = (a1, a2) => {
    let d = a2 - a1;
    while (d > Math.PI) d -= 2 * Math.PI;
    while (d < -Math.PI) d += 2 * Math.PI;
    const n = Math.ceil(Math.abs(d) / 0.1);
    for (let k = 1; k < n; k++) {
      const t = a1 + d * k / n;
      out.push([Math.cos(t), Math.sin(t), 0]);
    }
  };

  for (let i = 0; i < v.length; i++) {
    const a = v[i], b = v[(i + 1) % v.length], aVisible = a[2] >= 0, bVisible = b[2] >= 0;
    if (aVisible) out.push(a);
    if (aVisible !== bVisible) {
      const q = crossing(a, b), ang = Math.atan2(q[1], q[0]);
      if (aVisible) {
        exitAngle = ang;
        out.push(q);
      } else {
        if (exitAngle !== null) rimArc(exitAngle, ang);
        else firstEntryAngle = ang;
        out.push(q);
      }
    }
  }
  if (firstEntryAngle !== null && exitAngle !== null) rimArc(exitAngle, firstEntryAngle);

  ctx.beginPath();
  if (out.length < 3) return false;
  out.forEach((q, i) => {
    const X = cx + R * q[0], Y = cy - R * q[1];
    i ? ctx.lineTo(X, Y) : ctx.moveTo(X, Y);
  });
  ctx.closePath();
  return true;
}
