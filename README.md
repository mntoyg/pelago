# Pelago Asia

Pelago Asia is a Thai-language web prototype for a platform that tells small-scale fishers, every morning, **where fish
are likely to be, whether the sea is safe, and what the trip will cost in fuel**, using public satellite data. The
long-term goal is a service that works across Asia and reaches fishers through the chat app they already use (LINE,
Zalo, WhatsApp, Messenger, Telegram, Viber). It is being built for a hackathon (CodeAegis 2026); the current work
focus is **backend and AI**.

> **Status: front-end prototype.** This repository is a static web demo of the interface and the idea. It has no
> backend, no database, no chat integration, no legal/no-go zone filtering and no AI model. Spot positions, starting
> FSI values and the catch-journal rows are **demo data**, and the UI says so. It must not be used to decide where or
> whether to go to sea.

## What is in the prototype

- A satellite globe (NASA GIBS and Esri imagery) with drill-down: country → province → fishing spot, and layer toggles.
- A fish-suitability index (**FSI**, 0–100) per demo spot, computed in the browser from live NOAA ocean data (sea
  surface temperature, chlorophyll, depth) plus the moon phase. Starting weights are untuned.
- Twelve workspace screens: survey map, trip route, sea conditions and 7-day outlook, fuel cost calculator, catch
  journal, fish ID (mock-up), satellite data status, go / don't go, fish price at the landing, bloom warning (explainer),
  my pins, SOS (shows and copies coordinates only).
- Honest labelling: confidence labels, "trial" wording, and a data screen that shows which sources are really connected
  (for example the official weather agency feed is not).

## Documentation

| File | What it is |
| --- | --- |
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Target system (from the team's three reference documents) and how this prototype maps to it, with a gap analysis |
| [`TASK.md`](TASK.md) | Current status, backlog, open questions, review log |
| [`AGENTS.md`](AGENTS.md) | Rules for every AI agent and human working here: roles, remotes, conventions, how to verify, how to report |
| [`CLAUDE.md`](CLAUDE.md), [`CODEX.md`](CODEX.md) | Tool-specific notes that build on `AGENTS.md` |

## Where the product intent comes from

Three team documents (Thai) define the target. They are not stored in this repository; `ARCHITECTURE.md` summarises them
and cites the page numbers.

| Document | Date |
| --- | --- |
| *Build guide: satellite-based fishing-ground platform for all of Asia* (คู่มือสร้างแพลตฟอร์มหาแหล่งปลาด้วยดาวเทียมสำหรับทั่วเอเชีย) | 2026-11-21 |
| *Function specification for developers* (สเปกฟังก์ชันสำหรับพัฒนา แพลตฟอร์มหาแหล่งปลาทั่วเอเชีย) | 2026-11-24 |
| *Satellite and geospatial data sources for the prototype* (แหล่งข้อมูลดาวเทียมและภูมิสารสนเทศสำหรับต้นแบบ) | 2026-11-25 |

In short: 14 core functions (sign-up, daily data ingest, safety and no-go filter, FSI, morning recommendations, 7-day
outlook, route and fuel, tides, pins, catch log, fish ID, web map, mangrove monitoring, admin dashboard) plus extras
(go / don't go, fish prices, bloom warning, voice, SOS, many chat apps, many languages), delivered in five phases with
quality gates: Thailand first, then one country at a time. Four principles run through all of it: safety before
accuracy; never claim accuracy that has not been measured; usable with low literacy and weak internet; a fisher's data
belongs to the fisher.

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
- This is a public repository: no API keys, tokens, `.env` files or personal data, ever. A future backend keeps its keys
  in environment variables on the server.

## Data sources and attribution

The prototype uses these public, key-less services directly from the browser. Their terms apply to anyone who runs or
deploys it.

| Use | Source | Note |
| --- | --- | --- |
| Globe imagery | NASA GIBS (Blue Marble; chlorophyll, sea-surface-temperature and true-colour layers) | some layer ids are marked UNVERIFIED in `src/config.js` |
| Close-up imagery | Esri World Imagery (Esri, Maxar, Earthstar Geographics) | reference imagery, not live |
| Sea-surface temperature, chlorophyll, depth | NOAA CoastWatch ERDDAP (MUR SST, VIIRS chlorophyll, ETOPO 2022) | |
| Waves, wind | Open-Meteo Marine and Forecast | **free for non-commercial use only**; a commercial service needs another source |

Satellite-derived spots are estimates, not legal boundaries, and do not replace official announcements. See
`ARCHITECTURE.md` (A5, A7) for the safety rules and the licence notes for the full target system.
