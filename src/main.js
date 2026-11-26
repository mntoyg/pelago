// Entry point: exposes the inline-handler functions, then starts the app.
// Load order and layout of the modules is described in README.md ("Project structure").
import { $ } from './utils.js';
import { REFRESH_INTERVAL_MS } from './config.js';
import { ALL_SPOTS } from './data/spots.js';
import { view, target, runtime, reducedMotion } from './state.js';
import { resize } from './map/canvas.js';
import { goalForSelection, zoomBy } from './map/camera.js';
import { refreshImageryDate } from './map/tiles.js';
import { frame } from './map/globe.js';
import { initGlobeInput } from './map/input.js';
import { go, pickCountry, pickProvince } from './navigation.js';
import { loadWeekForecast } from './services/weather.js';
import { speak } from './services/device.js';
import { renderOverview } from './ui/overview.js';
import { renderSelection, toggleLayer } from './ui/sidebar.js';
import { prefetchSignals } from './ui/popup.js';
import { fuelInputs, renderFuelResult } from './ui/views.js';
import { show, mountBottomBar, addPrice, addPin, delPin, doSos } from './ui/workspace.js';

// The markup (index.html and the HTML built in src/ui/*) uses inline onclick/onchange/oninput attributes, which can
// only see globals. Every function or object those attributes call is listed here, under the name the markup uses.
Object.assign(window, {
  go, show, zoomBy,
  tg: toggleLayer,
  pickC: pickCountry,
  pickP: pickProvince,
  say: speak,
  addPr: addPrice,
  addPin, delPin, doSos,
  fu: renderFuelResult,
  M: fuelInputs,
});

// Daily imagery layers use yesterday's date; keep them (and the attribution line) current.
function refreshImagery() {
  const date = refreshImageryDate();
  $('.attr').textContent = 'ภาพล่าสุด: NASA VIIRS ' + date + ' · พื้นผิว: Blue Marble · Esri, Maxar, Earthstar Geographics · FSI และจุดปลาเป็นข้อมูลตัวอย่าง';
}

renderOverview();
refreshImagery();
setInterval(refreshImagery, REFRESH_INTERVAL_MS);
loadWeekForecast();
mountBottomBar();

// Re-fetch live sea data for every spot every 30 minutes.
setInterval(() => {
  ALL_SPOTS.forEach(entry => { entry.spot.signalPromise = null; });
  prefetchSignals();
}, REFRESH_INTERVAL_MS);

initGlobeInput();
show('survey');

// Opening camera: start zoomed in and rotated away, then fly to the Asia view.
addEventListener('resize', resize);
resize();
Object.assign(target, goalForSelection());
Object.assign(view, { ...target, R: target.R * 0.32, lo: target.lo - 80, la: target.la - 12 });
runtime.anim = reducedMotion ? null : { t0: performance.now(), d: 3200, h: 0, a: { ...view }, b: target };
if (reducedMotion) Object.assign(view, target);
renderSelection();
requestAnimationFrame(frame);
