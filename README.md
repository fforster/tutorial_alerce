# Tutorial ALeRCE Explorer (htmx)

Re-implementation of the ALeRCE Explorer using htmx + FastAPI + Jinja2 + Tailwind,
mirroring the patterns used in the production
[`alercebroker/web-services/multisurveys-apis`](https://github.com/alercebroker/web-services/tree/main/multisurveys-apis).

See `CLAUDE.md` for the overall design, reference implementations, and the
domain-specific traps (survey abstraction, 64-bit OIDs, ZTF→nJy normalization,
GLS periodogram, FITS rendering, etc.).

## Status

**Slice 1 — scaffolding.** The app boots, serves a shell page, and the htmx
routes return stub partials. Search, results, and object detail wiring against
the ALeRCE API come in the next slices.

## Install

```bash
# Python deps (Poetry)
poetry install

# Node deps (Tailwind CLI)
npm install

# Build the stylesheet (required before first run)
npm run build:css
```

## Run

```bash
poetry run uvicorn src.app:app --reload --port 8000
# or, with tailwind live-rebuild in another terminal:
npm run watch:css
```

Then open http://localhost:8000.

## Test

```bash
poetry run pytest
# or without poetry
PYTHONPATH=. pytest
```

## Layout

```
src/
  app.py                  FastAPI entrypoint
  routes/
    htmx.py               HTMLResponse endpoints (Jinja2 fragments)
    rest.py               JSON endpoints for client-side features
  services/
    survey_config.py      SC() dispatch + per-survey field remapping
    normalize.py          Raw detection → common schema (ZTF mag→nJy)
    safe_json.py          64-bit-OID-safe JSON parsing for LSST
    alerce_client.py      httpx client for the public ALeRCE API
  templates/              Jinja2 partials, grouped by feature sub-area
  static/
    css/tailwind.css      Tailwind entry; compiles to main.css
    js/helpers.js         send_form_Data / send_pagination_data / ...
    htmx/htmx.min.js      Self-hosted htmx 1.9.12
tests/                    pytest suite (service layer)
```
