// The globe canvas, its 2D context and its CSS-pixel size.
import { $ } from '../utils.js';

export const canvas = $('#c');
export const ctx = canvas.getContext('2d');
export const viewport = { w: 800, h: 600 };

// The globe is centred slightly above the middle of the map area.
export const GLOBE_CENTER_Y = 0.52;

// ctx.arc end angle: any value >= 2π draws a full circle.
export const FULL_CIRCLE = 7;

export function resize() {
  const rect = $('#map').getBoundingClientRect(), dpr = Math.min(devicePixelRatio || 1, 2);
  viewport.w = rect.width;
  viewport.h = rect.height;
  canvas.width = viewport.w * dpr;
  canvas.height = viewport.h * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
}
