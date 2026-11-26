// 7-day wave and wind forecast from Open-Meteo (free for non-commercial use).
// Data-access seam: replace loadWeekForecast() to source the forecast from a backend instead.
import { FORECAST_POINT, OPEN_METEO_MARINE_URL, OPEN_METEO_FORECAST_URL } from '../config.js';
import { sourceStatus } from './source-status.js';

// null until the forecast arrives (or if it fails); then { wave: [7 daily max wave heights, m], wind: [7 daily max
// wind speeds, km/h] }. Readers fall back to sample values while it is null. `export let` is a live binding.
export let weekForecast = null;

export async function loadWeekForecast() {
  try {
    const { lat, lon } = FORECAST_POINT;
    const [marine, forecast] = await Promise.all([
      fetch(`${OPEN_METEO_MARINE_URL}?latitude=${lat}&longitude=${lon}&daily=wave_height_max&timezone=auto`),
      fetch(`${OPEN_METEO_FORECAST_URL}?latitude=${lat}&longitude=${lon}&daily=wind_speed_10m_max&timezone=auto`),
    ]).then(responses => Promise.all(responses.map(r => r.json())));
    const wave = marine.daily.wave_height_max.slice(0, 7).map(v => +(+v || 0).toFixed(1));
    const wind = forecast.daily.wind_speed_10m_max.slice(0, 7).map(v => Math.round(+v || 0));
    if (wave.length === 7 && wind.length === 7) {
      weekForecast = { wave, wind };
      sourceStatus.wx = 1;
    }
  } catch (e) {
    sourceStatus.wx = -1;
  }
}
