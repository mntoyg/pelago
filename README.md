# pelago

Pelago Asia is a static, no-build web prototype that shows where fish are likely to be across Asian waters. It
combines a satellite globe, a fish-suitability index (FSI) and small tools for fishers (trip planner, sea
conditions, fuel cost, catch journal, go/no-go, SOS). All FSI values and spot positions are **demo data**.

## Run it

There is no build step and no dependencies. Serve the folder with any static server (ES modules need `http://`,
not `file://`):

```
python -m http.server 8000
```

Then open <http://localhost:8000>. Vercel deploys the folder as-is (`vercel.json`).

## Project structure

```
index.html            Page skeleton (header, sidebar, map overlays, #view container). IDs are used by the JS.
styles.css            All styles, in sections (tokens, header, sidebar, map overlays, workspace views, phone layout).
src/
  main.js             Entry point: exposes the functions used by inline onclick/oninput, then starts the app.
  config.js           External endpoints (NASA GIBS, Esri, NOAA ERDDAP, Open-Meteo), tile layers, FSI weights.
  state.js            Shared mutable state: selection (country/province/spot), camera, layers, per-frame state.
  navigation.js       go() / drill-down: selection -> camera target -> re-render.
  utils.js            Small helpers ($, number formatting, DEG).
  data/
    geography.js      Coastline polygons, Thailand outline, labels, star field (static, pure data).
    spots.js          DEMO countries -> provinces -> spots with FSI, plus the flat ALL_SPOTS list.
  services/           Data access. Replace these to plug in a backend or AI service.
    marine-data.js    Per-spot NOAA data + moon phase -> FSI v1 (fetchSpotSignal, computeFsi).
    weather.js        7-day wave/wind forecast from Open-Meteo.
    source-status.js  Connection status of each live source (shown on the data screen).
    device.js         localStorage lists, GPS, speech.
  map/                The canvas globe.
    canvas.js         Canvas, 2D context, viewport size.
    projection.js     Orthographic projection and horizon-clipped polygons.
    tiles.js          Tile cache and raster layer drawing.
    camera.js         Camera target per drill level, zoom.
    globe.js          The render loop (camera easing, layers, markers).
    input.js          Pointer drag, wheel zoom, hover and click on markers.
  ui/                 DOM rendering.
    sidebar.js        Sidebar, headline, breadcrumb, layer toggles (renderSelection).
    popup.js          Floating info card and live-data prefetch.
    overview.js       Date chip and time-of-day strip.
    layout.js         Workspace shell, page header, static tile map.
    views.js          The workspace screens (route, sea, fuel, log, fish, data, go, price, bloom, pins, sos).
    workspace.js      show() screen switching, nav bars, and the actions behind view buttons.
```

### Conventions

- The HTML built in `src/ui/*` uses inline `onclick`/`onchange`/`oninput` attributes. Every function they call must be
  listed in the `Object.assign(window, {...})` block in `src/main.js`.
- Data is demo-only and labelled as such in the UI. Keep the `DEMO DATA` / `UNVERIFIED` comments when editing.
- Where to plug in a backend: `src/data/spots.js` (spot list and FSI), `src/services/marine-data.js`
  (`fetchSpotSignal`) and `src/services/weather.js` (`loadWeekForecast`).
