# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project goal

Reproduce the ALeRCE Explorer using **htmx** (matching the stack of the original production ALeRCE explorer), based on an existing single-file JavaScript prototype. This repository is primarily a tutorial demonstrating Claude Code workflows on the ALeRCE project — correctness of the port matters, but the pedagogical framing (small, reviewable steps) is part of the point.

## Reference implementations

Two prior artifacts must be consulted before writing code here:

- **Feature / numerics source:** `../ALeRCE_explorer/alerce_explorer.html` — the single-file JS prototype (~5600 lines). Source of truth for UI layout, feature set, normalization logic, and numerical recipes (GLS periodogram, cosmology, FITS rendering, extinction). Its sibling `../ALeRCE_explorer/CLAUDE.md` has a detailed section map — consult it first when porting a specific feature.
- **htmx patterns source:** [`alercebroker/web-services/multisurveys-apis`](https://github.com/alercebroker/web-services/tree/main/multisurveys-apis) — the production ALeRCE web services. Mirror its htmx patterns (see below).

When porting a feature, read the corresponding line range in `alerce_explorer.html` rather than reimplementing from scratch — the normalization, error propagation, and survey-specific quirks have been debugged there.

## How ALeRCE uses htmx (patterns to mirror)

The production stack in `multisurveys-apis` is a **FastAPI + Jinja2 + htmx 1.9.12 + Tailwind CSS** application. Each feature area (object search, lightcurve, stamps, crossmatch, aladin, classifier, probability, magstat) is a separate FastAPI sub-app (microservice) under `src/<feature>_api/`, each with the same internal shape:

```
src/<feature>_api/
  api.py              # FastAPI() app, CORS, Prometheus, include_router(rest), include_router(htmx)
  routes/
    htmx.py           # endpoints returning HTMLResponse via Jinja2Templates
    rest.py (or json/) # endpoints returning JSON for programmatic clients
  services/           # business logic (DB queries, validators, parsers, idmapper, TNS, ...)
  models/             # Pydantic request/response models
  templates/          # Jinja2 partials, grouped by feature sub-area
  static/             # per-service CSS assets
```

Shared code lives under `src/core/` (config, exceptions, idmapper, htmx/htmx.min.js bundled locally, chart-js helpers, periodogram, repository). Each service is mounted on its own port via a YAML `services:` config consumed by `scripts/run_all.py`-style tooling; `API_URL` is injected into Jinja globals so templates build absolute URLs.

### The FastAPI + htmx contract

Each htmx endpoint takes filter query params, runs Pydantic/ad-hoc validation, calls a service function, and returns `templates.TemplateResponse(...)` with an HTML fragment. Example pattern from `object_api/routes/htmx.py`:

```python
router = APIRouter()
templates = Jinja2Templates(directory="src/object_api/templates", autoescape=True, auto_reload=True)
templates.env.globals["API_URL"] = os.getenv("API_URL", "http://localhost:8000")

@router.get("/htmx/list_objects", response_class=HTMLResponse)
def objects_table(request: Request, survey: str | None = None, ...):
    object_list = get_objects_list(session_ms=request.app.state.psql_session, search_params=...)
    return templates.TemplateResponse(
        name="main_table_objects/objects_table.html.jinja",
        context={"request": request, "objects_list": object_list, ...},
    )
```

Key endpoint families already implemented in production (reuse these names):

| Endpoint | Returns |
|---|---|
| `GET /htmx/search_objects/` | Filter form (survey toggle, classifier/class, probability, ndet range, dates, conesearch) |
| `GET /htmx/classes_select` | Dependent class `<select>` options for a chosen classifier |
| `GET /htmx/list_objects` | Main results table with pagination + sortable column headers |
| `GET /htmx/side_objects` | Sidebar list of objects (alternate view of the same results) |
| `GET /htmx/object_information` | Basic information panel for one object (oid + survey_id) |
| `GET /htmx/tns/` | TNS lookup by RA/Dec |

### Jinja template conventions

- Each fragment template starts by including `<script src="{{API_URL}}/htmx/htmx.min.js"></script>` and `<link rel="stylesheet" href="{{API_URL}}/static/...">` — htmx is **self-hosted**, not loaded from a CDN.
- Templates include `<meta name="htmx-config" content='{"selfRequestsOnly": false}'>` so the service can be embedded cross-origin.
- The `htmx-ext-response-targets` extension is loaded from unpkg for error-target routing.
- Tailwind classes are prefixed with `tw-` (configured in `tailwind.config.js`). Dark mode via `dark:` variants. Tailwind is compiled to `src/static/main.css` with `npm run build:css` / `watch:css`.
- Partials are small and composable; a feature area has a `templates/<feature>/` folder with multiple `.html.jinja` files plus a shared `input.html.jinja` macro (`{% from "input.html.jinja" import input as customInput %}`).

### htmx attribute idioms used throughout

- `hx-get="{{API_URL}}/htmx/list_objects"` with `hx-target="#objects_table"` and `hx-swap="outerHTML"` — endpoint returns the whole container so it can re-render itself (pagination links trigger this too).
- `hx-trigger="click"` on sortable `<th>` column headers and pagination spans.
- `hx-indicator="#table-objects-loading"` drives visible loading bars (`.loaderBar` class in `loading_indicators.css`).
- `hx-vals='js:{...send_form_Data(), ...send_pagination_data({{next}}), ...send_order_data(...)}'` — client-side JS helpers compose the query string from form state. This means **some client JS remains** to read DOM state and hand it back to htmx.
- `hx-ext="response-targets"` on the outer div so 4xx/5xx responses can target a different error region.
- Dependent dropdowns: the classifier `<span>` has `hx-get=".../classes_select" hx-trigger="change" hx-target="#classes_options" hx-swap="innerHTML" hx-vals='js:{...send_classes_data()}'`, so picking a classifier re-fetches the matching class options as an HTML fragment.

### Where client-side JS still lives

Even with htmx, these subsystems remain JS-heavy and should not be ported to server-rendered partials:

- Chart.js 4.x plots (light curve, radar, periodogram, folded, airmass) — the production stack bundles `chart.js` locally under `src/core/chart-js/` with `helpers/` modules (our port should do the same rather than pull from a CDN).
- P4J / GLS periodogram (production uses the `P4J` Python wheel for offline jobs, but the UI still needs an in-browser periodogram for interactive phase folding — keep the GLS implementation from the prototype).
- In-browser FITS parsing + stamp rendering (asinh stretch, WCS rotation) for LSST stamps.
- Aladin Lite sky viewer.
- Zoom/pan gestures (`chartjs-plugin-zoom`, `Hammer.js`).
- Keyboard / touch navigation between objects in the result list.
- The small JS helpers that produce `hx-vals` payloads (`send_form_Data`, `send_pagination_data`, `send_order_data`, `send_classes_data`, etc.).

### Good targets for server-rendered htmx fragments

Search results table, object metadata panel, filter accordion state, crossmatch table, external archives dropdown, airmass observatory picker, classifier/class dropdowns (which depend on the survey), TNS side-panel.

## Domain complexity that is NOT obvious

These are the traps — read the referenced sections in `../ALeRCE_explorer/CLAUDE.md` before touching them:

1. **Survey abstraction via `SURVEY_CONFIG`** — LSST and ZTF use different field names, endpoints, and band sets. Never branch on survey directly; add entries to the config table.
2. **Normalization contract** — ZTF detections arrive in magnitudes and must be converted to nJy (`psfFlux = 10^((31.4 - mag)/2.5)`); LSST arrives in nJy already. Visualization consumes normalized data only.
3. **LSST OIDs are 64-bit integers** — `JSON.parse` silently loses precision. Use the `safeJsonParse` regex-wrap approach for every LSST response containing OIDs; compare candids as strings.
4. **ZTF v1/v2 lightcurve merge** — `mag_corr`/`e_mag_corr` come from the v2 endpoint and must be joined to v1 detections by candid string; `e_mag_corr = 100.0` is a sentinel for "unreliable" and any value ≥ 1.0 should be rejected.
5. **Light-curve display toggles are independent and composable** (flux/mag × diff/sci × apparent/absolute × observed/dereddened × band visibility × band offset × phase folding). A single `getPlotY` function applies all active corrections; don't scatter this logic.
6. **Cosmology** — Planck 2018 (H0=67.4, Ωm=0.315); distance modulus is computed by numeric integration, not a closed form.
7. **Milky Way extinction** — E(B-V) is fetched from a Cloudflare Workers proxy to IRSA; cache by RA/Dec rounded to 0.01°; Fitzpatrick (1999) R_λ coefficients are stored per survey.
8. **FITS pipeline** — gzip detection by magic bytes, 2880-byte block parsing, BZERO/BSCALE, asinh stretch on z-scaled percentiles, Y-flip only when `CDELT2 > 0`, North-up rotation via the CD matrix.
9. **Periodogram** — Generalized Lomb-Scargle with inverse-variance weighting, frequency grid `df = 1/(oversample·T)`, time-centered to reduce trig-argument magnitude, multi-harmonic score (sum of power at 1f–6f, NH=6) to suppress aliases, parabolic peak refinement.
10. **HiPS probing** — uses FITS cutouts (not JPEG) so compression artifacts don't fake coverage.

## External services the port depends on

- ALeRCE API (LSST and ZTF variants — distinct `apiBase`, `objectsUrl`, `lcUrl`, `fpUrl`, `probUrl`). The production microservices in `multisurveys-apis` are the canonical implementations; depending on how far the tutorial goes, we either call those APIs as a client or re-host a FastAPI sub-app that proxies them.
- ALeRCE stamp service (`avro.alerce.online/get_stamp` for ZTF PNG; `stamps_api/stamp` for LSST FITS).
- `catshtm.alerce.online/crossmatch_all` for catalog crossmatch.
- IRSA dust map via `dust-proxy.francisco-forster.workers.dev` (Cloudflare Worker).
- CDS: `hips2fits` (HiPS cutouts), Sesame name resolver, Aladin Lite CDN.

## Recommended stack for this tutorial

To stay close to the production htmx pattern while keeping the tutorial small, aim for:

- **Python 3.11**, **FastAPI**, **Jinja2** (`auto_reload=True` in dev), **htmx 1.9.12 self-hosted**, **Tailwind 3.4+** via `tailwindcss` CLI, Poetry for deps.
- Single FastAPI app first (not microservices) with `routes/htmx.py` returning `HTMLResponse` and `routes/rest.py` (or `json/`) returning JSON where we need to call the ALeRCE API client-side.
- `templates/` organized by feature sub-area, plus a shared `input.html.jinja` macro.
- `static/` for compiled Tailwind CSS and any client JS helpers (`send_form_Data`, chart rendering, FITS parser, Aladin bootstrap).
- Client JS helpers attach data via `hx-vals='js:{...helper()}'` rather than storing filter state on the server.

## Repository status

No source files, build configuration, or tests exist yet. Once scaffolding is in place (backend framework, template layout, static assets), re-run `/init` so this file can be extended with real build/lint/test commands and the final architecture overview.
