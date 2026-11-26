// The render loop: camera easing, then every layer of the globe, back to front.
import { $, DEG } from '../utils.js';
import { view, target, selection, runtime, reducedMotion, layers, markersInScope } from '../state.js';
import { ALL_SPOTS } from '../data/spots.js';
import { LAND_POLYGONS, THAILAND_OUTLINE, COUNTRY_LABELS, SEA_LABELS, STARS } from '../data/geography.js';
import { ctx, viewport, GLOBE_CENTER_Y, FULL_CIRCLE } from './canvas.js';
import { project, tracePolygon } from './projection.js';
import { drawTiles } from './tiles.js';
import { placePopup } from '../ui/popup.js';

const FONT = '"Noto Sans Thai",sans-serif';

// Marker colour by FSI band.
const fsiColor = fsi => fsi >= 80 ? '#7bf0c8' : fsi >= 74 ? '#2dd4bf' : '#6cc3d9';

// Quality governor: drops effects when frames are slow. 2 = everything, 1 = no land glow, 0 = no stars/pulses/glow.
let quality = 2;
let avgFrameMs = 16, lastFrameTime = 0, lastQualityDrop = 0;

export function frame(t) {
  const W = viewport.w, H = viewport.h;
  let flight = 0;   // 0..1 arc of a fly-to animation; drives the vignette and hides the popup mid-flight

  // --- frame-time tracking ---
  {
    const dt = Math.min(t - lastFrameTime, 100);
    if (lastFrameTime && dt > 0) {
      avgFrameMs = avgFrameMs * 0.94 + dt * 0.06;
      if (avgFrameMs > 40 && quality > 0 && t - lastQualityDrop > 2500) { quality--; lastQualityDrop = t; avgFrameMs = 16; }
    }
    lastFrameTime = t;
  }

  // --- camera: either follow the fly-to animation, or ease towards the target ---
  const anim = runtime.anim;
  if (anim) {
    const u = Math.min(1, Math.max(0, (t - anim.t0) / anim.d));
    const e = u < 0.5 ? 4 * u * u * u : 1 - Math.pow(-2 * u + 2, 3) / 2;   // ease-in-out cubic
    const a = anim.a, b = anim.b;
    const dist = Math.hypot(b.lo - a.lo, b.la - a.la);
    const hop = anim.h !== undefined ? anim.h : 0.15 + 0.4 * Math.min(1, dist / 20);   // zoom-out "hop" mid-flight
    view.lo = a.lo + (b.lo - a.lo) * e;
    view.la = a.la + (b.la - a.la) * e;
    view.R = Math.exp(Math.log(a.R) + (Math.log(b.R) - Math.log(a.R)) * e - hop * Math.sin(Math.PI * u));
    flight = anim.h !== undefined ? 0 : Math.sin(Math.PI * u);
    if (u >= 1) runtime.anim = null;
  } else {
    const k = reducedMotion ? 1 : 0.085;
    if (!selection.country && !runtime.drag && !reducedMotion) target.lo += 0.012;   // slow idle spin
    view.lo += (target.lo - view.lo) * k;
    view.la += (target.la - view.la) * k;
    view.R *= Math.pow(target.R / view.R, k);
  }

  // --- sky: background and stars ---
  ctx.fillStyle = '#05111a';
  ctx.fillRect(0, 0, W, H);
  const inSpace = view.R < Math.max(W, H) ? 1 : 0;   // whole globe is visible
  if (inSpace && quality > 0) {
    STARS.forEach(s => {
      ctx.globalAlpha = s[2] * (0.7 + 0.3 * Math.sin(t / 1500 + s[0] * 40));
      ctx.fillStyle = '#cfeee8';
      ctx.fillRect(s[0] * W, s[1] * H, s[3], s[3]);
    });
  }
  ctx.globalAlpha = 1;

  // --- ground shadow, ocean sphere, atmosphere ---
  const cx = W / 2, cy = H * GLOBE_CENTER_Y;
  if (inSpace) {
    ctx.save();
    ctx.translate(cx, cy + view.R * 1.12);
    ctx.scale(1, 0.16);
    const shadow = ctx.createRadialGradient(0, 0, 0, 0, 0, view.R);
    shadow.addColorStop(0, '#000c');
    shadow.addColorStop(1, '#0000');
    ctx.fillStyle = shadow;
    ctx.beginPath();
    ctx.arc(0, 0, view.R, 0, FULL_CIRCLE);
    ctx.fill();
    ctx.restore();
  }
  const ocean = ctx.createRadialGradient(cx - view.R * 0.25, cy - view.R * 0.3, view.R * 0.1, cx, cy, view.R);
  ocean.addColorStop(0, '#1c5a6c');
  ocean.addColorStop(0.5, '#0f3343');
  ocean.addColorStop(0.88, '#081d29');
  ocean.addColorStop(1, '#040d14');
  ctx.fillStyle = ocean;
  ctx.beginPath();
  ctx.arc(cx, cy, view.R, 0, FULL_CIRCLE);
  ctx.fill();
  if (view.R < Math.max(W, H)) {
    const glow = ctx.createRadialGradient(cx, cy, view.R * 0.97, cx, cy, view.R * 1.12);
    glow.addColorStop(0, '#5ff0e099');
    glow.addColorStop(1, '#3fd0c000');
    ctx.fillStyle = glow;
    ctx.beginPath();
    ctx.arc(cx, cy, view.R * 1.12, 0, FULL_CIRCLE);
    ctx.fill();
  }

  // --- graticule (every 10 degrees) ---
  ctx.lineWidth = 1;
  ctx.strokeStyle = '#4aa8b01c';
  for (let lat = -80; lat <= 80; lat += 10) {
    ctx.beginPath();
    let pen = false;
    for (let lon = -180; lon <= 180; lon += 3) {
      const p = project(lon, lat);
      if (p[2] > 0.02) { pen ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]); pen = true; } else pen = false;
    }
    ctx.stroke();
  }
  for (let lon = -180; lon < 180; lon += 10) {
    ctx.beginPath();
    let pen = false;
    for (let lat = -85; lat <= 85; lat += 3) {
      const p = project(lon, lat);
      if (p[2] > 0.02) { pen ? ctx.lineTo(p[0], p[1]) : ctx.moveTo(p[0], p[1]); pen = true; } else pen = false;
    }
    ctx.stroke();
  }

  // --- land: glow, then fill + outline ---
  if (quality > 1) {
    ctx.save();
    ctx.shadowColor = '#2dd4bf';
    ctx.shadowBlur = Math.min(46, view.R * 0.05 + 10);
    ctx.fillStyle = '#0f3a45';
    LAND_POLYGONS.forEach(poly => { if (tracePolygon(poly)) ctx.fill(); });
    ctx.restore();
  }
  const landFill = ctx.createLinearGradient(0, 0, W, H);
  landFill.addColorStop(0, '#2f726c');
  landFill.addColorStop(0.5, '#1d5658');
  landFill.addColorStop(1, '#143f46');
  ctx.fillStyle = landFill;
  ctx.strokeStyle = '#86e6d4';
  ctx.lineWidth = 1.1;
  LAND_POLYGONS.forEach(poly => { if (tracePolygon(poly)) { ctx.fill(); ctx.stroke(); } });

  // --- satellite tiles, then the Thailand outline when zoomed in without imagery ---
  drawTiles();
  if (view.R > 900 && !layers.img) {
    ctx.fillStyle = '#2b6a64';
    ctx.strokeStyle = '#8ff0dc';
    ctx.lineWidth = 1.6;
    if (tracePolygon(THAILAND_OUTLINE)) { ctx.fill(); ctx.stroke(); }
  }

  // --- limb shading ---
  if (inSpace) {
    const shade = ctx.createRadialGradient(cx - view.R * 0.35, cy - view.R * 0.4, view.R * 0.15, cx, cy, view.R);
    shade.addColorStop(0, '#0000');
    shade.addColorStop(0.7, '#0000');
    shade.addColorStop(1, '#000b');
    ctx.fillStyle = shade;
    ctx.beginPath();
    ctx.arc(cx, cy, view.R, 0, FULL_CIRCLE);
    ctx.fill();
  }

  // --- plankton / FSI glow under every spot ---
  ctx.globalCompositeOperation = 'lighter';
  (quality > 0 ? ALL_SPOTS : []).forEach(entry => {
    const p = project(entry.spot.coord[0], entry.spot.coord[1]);
    if (p[2] <= 0) return;
    const r = Math.max(34, view.R * DEG * (0.9 + entry.spot.fsi / 150)) * (1 + 0.04 * Math.sin(t / 900 + entry.spot.fsi));
    const g = ctx.createRadialGradient(p[0], p[1], 0, p[0], p[1], r);
    g.addColorStop(0, '#2dd4bf3a');
    g.addColorStop(0.5, '#2dd4bf14');
    g.addColorStop(1, '#2dd4bf00');
    ctx.fillStyle = g;
    ctx.beginPath();
    ctx.arc(p[0], p[1], r, 0, FULL_CIRCLE);
    ctx.fill();
  });
  ctx.globalCompositeOperation = 'source-over';

  // --- sea names and country labels ---
  ctx.textAlign = 'center';
  ctx.font = '500 10px ' + FONT;
  ctx.fillStyle = '#5fa8b4';
  ctx.font = 'italic 400 11px ' + FONT;
  SEA_LABELS.forEach(([name, lo, la]) => {
    const p = project(lo, la);
    if (p[2] > 0.3 && view.R < 9000) ctx.fillText(name, p[0], p[1]);
  });
  ctx.font = '500 10px ' + FONT;
  if (view.R < 2600) {
    ctx.fillStyle = '#7fa3a8aa';
    try { ctx.letterSpacing = '2px'; } catch (e) { /* letterSpacing unsupported: draw without it */ }
    COUNTRY_LABELS.forEach(([name, lo, la]) => {
      const p = project(lo, la);
      if (p[2] > 0.25) ctx.fillText(name, p[0], p[1]);
    });
    try { ctx.letterSpacing = '0px'; } catch (e) { /* see above */ }
  }

  // --- markers for the current drill level ---
  runtime.hits = [];
  markersInScope().forEach((marker, i) => {
    const spot = marker.spot, p = project(spot.coord[0], spot.coord[1]);
    if (p[2] <= 0) return;
    const active = (selection.spot != null && marker.spotIndex === selection.spot) || (runtime.focus && runtime.focus.spot === spot);
    const color = fsiColor(spot.fsi);
    const phase = reducedMotion ? 0.5 : (t / 1100 + i * 0.3) % 1;
    // pulse rings
    for (let j = 0; j < (quality > 0 ? 3 : 0); j++) {
      const q = (phase + j / 3) % 1;
      ctx.strokeStyle = color;
      ctx.globalAlpha = (1 - q) * (1 - q) * 0.9;
      ctx.lineWidth = 2.4 * (1 - q) + 0.6;
      ctx.beginPath();
      ctx.arc(p[0], p[1], 10 + q * (34 + spot.fsi * 0.25), 0, FULL_CIRCLE);
      ctx.stroke();
    }
    ctx.globalAlpha = quality > 0 ? 0.22 + 0.22 * Math.sin(t / 200 + i * 2) : 0;
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(p[0], p[1], 17, 0, FULL_CIRCLE);
    ctx.fill();
    ctx.globalAlpha = 1;
    // pin stem whose height grows with FSI
    const stem = 16 + spot.fsi * 0.55, stemGradient = ctx.createLinearGradient(0, p[1], 0, p[1] - stem);
    stemGradient.addColorStop(0, color);
    stemGradient.addColorStop(1, '#0000');
    ctx.strokeStyle = stemGradient;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(p[0], p[1]);
    ctx.lineTo(p[0], p[1] - stem);
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();
    ctx.arc(p[0], p[1] - stem, 2.5, 0, FULL_CIRCLE);
    ctx.fill();
    ctx.globalAlpha = 1;
    // numbered badge
    ctx.fillStyle = '#08222b';
    ctx.strokeStyle = color;
    ctx.lineWidth = active ? 3 : 1.8;
    ctx.beginPath();
    ctx.arc(p[0], p[1], 11 + 1.3 * Math.sin(t / 240 + i), 0, FULL_CIRCLE);
    ctx.fill();
    ctx.stroke();
    ctx.fillStyle = color;
    ctx.font = '700 11px ' + FONT;
    ctx.fillText(String(i + 1), p[0], p[1] + 4);
    ctx.textAlign = 'left';
    ctx.font = '500 10.5px ' + FONT;
    ctx.fillStyle = '#d9f2ee';
    ctx.fillText('FSI ' + spot.fsi, p[0] + 17, p[1] + 4);
    ctx.textAlign = 'center';
    runtime.hits.push({ x: p[0], y: p[1], marker });
  });

  // --- vignette during fly-to animations ---
  if (flight > 0.01) {
    const vignette = ctx.createRadialGradient(cx, cy, Math.min(W, H) * 0.25, cx, cy, Math.max(W, H) * 0.75);
    vignette.addColorStop(0, '#0000');
    vignette.addColorStop(1, 'rgba(2,10,16,' + (flight * 0.65) + ')');
    ctx.fillStyle = vignette;
    ctx.fillRect(0, 0, W, H);
  }

  $('#pop').style.opacity = flight > 0.05 ? 0 : 1;
  placePopup();
  requestAnimationFrame(frame);
}
