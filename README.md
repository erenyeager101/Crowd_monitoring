# Crowd Management & Monitoring Platform

A **modular, production-ready** crowd management and monitoring system with provider-agnostic crowd estimation, automatic fallback chain, and real-time dashboard.

---

## Table of Contents
1. [Architecture](#architecture)
2. [Quick Start](#quick-start)
3. [Environment Variables](#environment-variables)
4. [Provider Configuration](#provider-configuration)
5. [Fallback Behavior](#fallback-behavior)
6. [API Reference](#api-reference)
7. [Observability](#observability)
8. [Testing](#testing)
9. [Docker Deployment](#docker-deployment)
10. [Migration from Legacy OpenCV Flow](#migration-from-legacy-opencv-flow)
11. [Troubleshooting](#troubleshooting)
12. [Security](#security)

---

## Architecture

```
crowd_engine/ (Python package)
├── domain/
│   ├── entities.py     → CrowdEstimate, CameraInput
│   └── interfaces.py   → CrowdCountProvider (Protocol)
├── providers/
│   ├── roboflow_provider.py   ← PRIMARY  (API, free tier)
│   ├── huggingface_provider.py← SECONDARY (local OSS model)
│   ├── geospatial_provider.py ← TERTIARY (OSM heuristic proxy)
│   └── opencv_provider.py     ← FALLBACK (legacy MobileNetSSD)
├── services/
│   ├── orchestrator.py  → FallbackOrchestrator
│   ├── health.py        → HealthService
│   └── factory.py       → build_orchestrator()
├── infra/
│   ├── config.py  → Settings (env-var backed, typed)
│   └── logger.py  → Structured logging + correlation IDs
└── __main__.py    → CLI entry point

api_server.py      → FastAPI REST API (OpenAPI docs at /docs)
server.js          → Node.js dashboard (existing, enhanced)
tests/
├── unit/          → Provider + orchestrator + entity tests
└── integration/   → API endpoint contract tests
```

### Key design decisions

| Decision | Rationale |
|----------|-----------|
| Provider Protocol (structural typing) | Zero-coupling — add new providers without touching orchestrator |
| Fallback chain configured via env var | Ops can swap provider order without code changes |
| Circuit breaker per provider | Prevents cascade failures if one API goes down |
| FastAPI for Python API layer | OpenAPI docs out-of-the-box, async-ready, typed |
| Keep Node.js dashboard intact | Preserves existing frontend; Python engine is plugged in |

---

## Quick Start

### Prerequisites
- Python 3.11+
- Node.js 20+
- MongoDB (local or Atlas)

### 1. Clone and install

```bash
git clone https://github.com/erenyeager101/Crowd_monitoring.git
cd Crowd_monitoring

pip install -r requirements.txt
npm install
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env — set MONGO_URI and optionally ROBOFLOW_API_KEY
```

### 3. Start services

```bash
# Terminal 1 — Node.js dashboard (port 3000)
npm run start-node

# Terminal 2 — Python crowd estimation API (port 8000)
uvicorn api_server:app --port 8000

# Terminal 3 — Crowd detection engine (reads cameras.json)
python -m crowd_engine --cameras cameras.json
```

- **Dashboard (main):** http://localhost:3000/crowd
- **Admin / Login:** http://localhost:3000/
- **API docs:** http://localhost:8000/docs

---

## Frontend Dashboard

The dashboard (`public/index.html`) is a single-page app with sidebar navigation that surfaces all available backend data.

### Pages / Sections

| Section | Navigation | Data Source |
|---------|------------|-------------|
| Overview | Default view at `/crowd` | `GET /data` — KPI cards, recent readings table, 3 real-time charts |
| Live Map | Click "Live Map" in sidebar | `GET /data` — Leaflet map with colour-coded crowd markers |
| Shops | Click "Shops" in sidebar | `GET /shops` + `GET /data` — Table of registered shops with live crowd status |
| Trends & Charts | Click "Trends & Charts" in sidebar | `GET /data` — Time-series charts; shop comparison from `/api/historical-data` |
| Top Locations | Click "Top Locations" in sidebar | `GET /api/top-shops` — Bar chart + ranking table |
| Heatmap Data | Click "Heatmap Data" in sidebar | `GET /api/heatmap` — Grid view with density bars |
| History | Click "History" in sidebar | `GET /history?shop=&time=` — Per-shop historical chart + table |
| System Health | Click "System Health" in sidebar | `GET /health` (Node.js) + `GET http://localhost:8000/health` (Python) + `/api/v1/orchestrator/health` |

### Features

- **Dark-mode responsive UI** — sidebar collapses to hamburger on mobile.
- **Loading / empty / error states** — every data-driven view shows a spinner, empty illustration, or error message.
- **Live updates** — crowd data auto-refreshes every 5 seconds.
- **Status badges** — colour-coded Low / Moderate / High crowd indicators on every reading.
- **Inline search / filter** — Recent readings and Shops tables both support client-side text search.
- **Shop comparison chart** — choose two locations and load their historical crowd trends side-by-side.
- **Map search** — type a shop name to zoom the Leaflet map to that location.

### Running the Frontend

```bash
# Just the Node.js server (serves the dashboard at :3000)
npm start

# With Python API for advanced estimation (optional, adds System Health data)
uvicorn api_server:app --port 8000 --reload
```

The frontend degrades gracefully if the Python API is not running — all Node.js endpoints still work and the System Health section shows a clear "offline" message.

---

## Environment Variables

Copy `.env.example` to `.env`. **Never commit `.env` to version control.**

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URI` | `mongodb://localhost:27017` | MongoDB connection string |
| `PORT` | `3000` | Node.js server port |
| `API_PORT` | `8000` | Python API port |
| `API_SECRET_KEY` | `changeme` | Change in production |
| `PROVIDER_CHAIN` | `roboflow,huggingface,geospatial,opencv` | Ordered fallback chain |
| `ROBOFLOW_API_KEY` | *(empty)* | Free-tier key from roboflow.com |
| `HF_MODEL` | `facebook/detr-resnet-50` | HuggingFace model |
| `HF_API_KEY` | *(empty)* | HuggingFace Inference API key |
| `OPENCV_PROTOTXT` | `MobileNetSSD_deploy.prototxt` | Model proto path |
| `OPENCV_CAFFEMODEL` | `MobileNetSSD_deploy.caffemodel` | Model weights path |
| `PROVIDER_TIMEOUT_SECONDS` | `10.0` | Per-provider timeout |
| `PROVIDER_MAX_RETRIES` | `2` | Retries per provider |
| `CIRCUIT_BREAKER_THRESHOLD` | `3` | Failures before circuit opens |
| `CIRCUIT_BREAKER_RESET_SECONDS` | `60` | Auto-reset after N seconds |
| `LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING / ERROR |
| `LOG_JSON` | `false` | true = JSON-line logs (production) |
| `RATE_LIMIT_PER_MINUTE` | `60` | API rate limit per IP |

---

## Provider Configuration

### Provider Chain

```bash
# Production (full chain)
PROVIDER_CHAIN=roboflow,huggingface,geospatial,opencv

# Offline / no API keys
PROVIDER_CHAIN=huggingface,opencv

# Development only
PROVIDER_CHAIN=opencv
```

### Roboflow (Primary API provider)
- **Free tier:** Yes — sign up at roboflow.com
- **Accuracy:** High
- **Latency:** 200–500 ms
- Set `ROBOFLOW_API_KEY`

### HuggingFace (Secondary — local open-source model)
- **Free tier:** Yes — no API key for local inference
- **Model:** `facebook/detr-resnet-50` (Apache 2.0, COCO)
- **First run:** Downloads ~170 MB model
- **Latency:** 1–5 s CPU, ~200 ms GPU
- Requires `transformers` + `torch` (in requirements.txt)

### Geospatial/OSM (Tertiary — proxy)
- **Free tier:** Yes — OpenStreetMap Nominatim, no key
- **Accuracy:** Low (heuristic, not real-time)
- **Confidence:** Capped at 0.35 (clearly marked)

### OpenCV/MobileNetSSD (Last-resort fallback)
- Fully offline — requires model files in project root
- Confidence fixed at 0.60 (degraded-mode marker)

---

## Fallback Behavior

```
[Roboflow] → fail → [HuggingFace] → fail → [Geospatial] → fail → [OpenCV] → fail → error estimate
```

**Circuit breaker:** After N consecutive failures, a provider is bypassed for 60 s before retrying.

**Retries:** Each provider is retried up to `PROVIDER_MAX_RETRIES` times with exponential back-off before falling back.

---

## API Reference

Full interactive docs at `http://localhost:8000/docs`.

### `POST /api/v1/estimate`

```json
// Request
{
  "latitude": 18.52,
  "longitude": 73.85,
  "source": "rtsp://192.168.1.10:8080/video",
  "label": "Main Entrance"
}

// Response
{
  "count": 12,
  "confidence": 0.87,
  "timestamp": "2024-01-15T10:30:00+00:00",
  "source": "roboflow",
  "camera_id": "uuid",
  "latitude": 18.52,
  "longitude": 73.85,
  "metadata": {},
  "error": null
}
```

### Other endpoints
| Endpoint | Description |
|----------|-------------|
| `GET /health` | Provider health + aggregate status |
| `GET /api/v1/orchestrator/health` | Metrics: fallback rate, circuit state |
| `GET /readyz` | Kubernetes readiness probe |
| `GET /livez` | Kubernetes liveness probe |
| `GET /docs` | Swagger UI |

---

## Observability

### Structured Logs

```bash
LOG_JSON=true  # enables JSON-line output
```

Example log line:
```json
{"timestamp":"2024-01-15T10:30:00Z","level":"INFO","message":"Provider roboflow returned valid estimate","count":12,"correlation_id":"abc-123"}
```

### Correlation IDs

Pass `X-Correlation-ID` header; it is echoed back and injected into all log lines.

### Metrics

`GET /api/v1/orchestrator/health` returns:
- `total_requests`, `fallback_count`, `fallback_rate`
- Per-provider: `success`, `failure`, `timeout`, `circuit_open`

---

## Testing

```bash
# All tests
python -m pytest

# Unit tests (no external calls)
python -m pytest tests/unit/ -v

# Integration tests (API contracts)
python -m pytest tests/integration/ -v
```

---

## Docker Deployment

```bash
# Start all services
docker compose up --build

# Stop
docker compose down
```

---

## Migration from Legacy OpenCV Flow

| Before | After |
|--------|-------|
| `detection.py` — monolithic OpenCV | `crowd_engine/` — modular, provider-agnostic |
| Hard-coded MongoDB URI in source | `MONGO_URI` env var |
| No fallback | 4-provider fallback chain |
| No error handling | Circuit breaker + retry + structured errors |
| No REST API | FastAPI with OpenAPI docs |
| No tests | 42 tests (unit + integration) |
| No Docker | `Dockerfile` + `docker-compose.yml` |

```bash
# Old
python detection.py

# New
python -m crowd_engine --cameras cameras.json

# Health check
python -m crowd_engine --health
```

The original `detection.py` is preserved unchanged. The OpenCV MobileNetSSD logic lives in `crowd_engine/providers/opencv_provider.py` as the last-resort fallback.

---

## Troubleshooting

**All providers failed:** Run `python -m crowd_engine --health` to see status.

**Roboflow 401:** Check `ROBOFLOW_API_KEY`.

**HuggingFace slow (first run):** Expected — downloading model. Subsequent runs use cache.

**Circuit breaker tripping:** Provider is consistently failing. Check `/api/v1/orchestrator/health` and remove failing provider from `PROVIDER_CHAIN`.

---

## Security

- **Passwords:** Currently stored in plain text — add bcrypt hashing before production.
- **API keys:** Store in `.env` or a secrets manager. Never commit to source control.
- **CORS:** Configured for `*` in dev. Restrict `allow_origins` in production.
- **Rate limiting:** 60 req/min per IP by default. Tune `RATE_LIMIT_PER_MINUTE`.
- **Security headers:** `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security` set on all API responses.
