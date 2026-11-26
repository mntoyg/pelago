// Pointer input on the globe: drag to rotate, wheel to zoom, hover to focus a marker, click to drill down.
import { $, DEG } from '../utils.js';
import { view, target, runtime } from '../state.js';
import { canvas, viewport, GLOBE_CENTER_Y } from './canvas.js';
import { zoomBy } from './camera.js';
import { setFocus } from '../ui/popup.js';
import { drill } from '../navigation.js';

// Marker under the pointer (within 22 px), if any.
const markerAt = e => {
  const r = canvas.getBoundingClientRect();
  return runtime.hits.find(h => Math.hypot(h.x - (e.clientX - r.left), h.y - (e.clientY - r.top)) < 22);
};

// Coordinate read-out under the pointer. The #hud element is currently hidden by CSS but is kept up to date.
function updateHud(e) {
  const r = canvas.getBoundingClientRect(), X = e.clientX - r.left - viewport.w / 2, Y = -(e.clientY - r.top - viewport.h * GLOBE_CENTER_Y);
  const rho = Math.hypot(X, Y), el = $('#hud');
  if (!rho || rho > view.R) { el.textContent = ''; return; }
  const c = Math.asin(rho / view.R), p0 = view.la * DEG;
  const lat = Math.asin(Math.cos(c) * Math.sin(p0) + Y * Math.sin(c) * Math.cos(p0) / rho);
  const lon = view.lo + Math.atan2(X * Math.sin(c), rho * Math.cos(p0) * Math.cos(c) - Y * Math.sin(p0) * Math.sin(c)) / DEG;
  const metresPerPx = 6371000 / view.R;
  el.textContent = Math.abs(lat / DEG).toFixed(3) + '° ' + (lat < 0 ? 'S' : 'N') + ', ' + lon.toFixed(3) + '° E · 1 px ≈ ' +
    (metresPerPx >= 1000 ? (metresPerPx / 1000).toFixed(1) + ' กม.' : metresPerPx.toFixed(0) + ' ม.');
}

export function initGlobeInput() {
  canvas.addEventListener('pointerdown', e => {
    runtime.drag = { x: e.clientX, y: e.clientY, m: 0 };   // m = total movement, to tell a click from a drag
    canvas.setPointerCapture(e.pointerId);
    canvas.style.cursor = 'grabbing';
  });
  canvas.addEventListener('pointermove', e => {
    const drag = runtime.drag;
    if (drag) {
      runtime.anim = null;
      const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
      drag.x = e.clientX;
      drag.y = e.clientY;
      drag.m += Math.abs(dx) + Math.abs(dy);
      const k = 1 / (view.R * DEG);
      target.lo -= dx * k / Math.max(0.35, Math.cos(view.la * DEG));
      target.la = Math.max(-70, Math.min(70, target.la + dy * k));
      return;
    }
    const hit = markerAt(e);
    if (hit) setFocus(hit.marker);
    updateHud(e);
  });
  canvas.addEventListener('pointerup', e => {
    canvas.style.cursor = 'grab';
    if (runtime.drag && runtime.drag.m < 5) {
      const hit = markerAt(e);
      if (hit) drill(hit.marker);
    }
    runtime.drag = null;
  });
  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    zoomBy(e.deltaY < 0 ? 1.18 : 1 / 1.18);
  }, { passive: false });
}
