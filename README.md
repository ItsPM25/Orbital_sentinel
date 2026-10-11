# Orbital Sentinel

Early-warning health monitoring for satellite fleets: telemetry anomaly detection, explanation and risk ranking, shown on a live 3D globe.

> **What this is.** A proof of concept for decision support. It **detects anomalies** as they unfold; it does not forecast failures. Health telemetry is a **historical replay** of NASA's public SMAP/MSL dataset; only orbital positions are live. It must not be used as the basis for real spacecraft operations.

**Status:** Phases 0–4 are code-complete and tested (foundation, detector choice, detection pipeline, explanation/prioritisation, dashboard). Two real-data reports (the baseline accuracy report and the persistence-filter comparison) are still pending the 81-channel training run finishing. See [docs/PHASES.md](docs/PHASES.md) for the plan and status notes, and [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design.

## Layout

| Folder | What |
|---|---|
| `web/` | Next.js + React frontend (port 3001) |
| `backend/` | FastAPI backend, database models, pipeline code (port 8000) |
| `ml/` | Model experiments (`ml/spike/` is the Phase 1 spike) |
| `data/` | NASA SMAP/MSL dataset (not in git; see below) |
| `models/` | Trained model weights (not in git; see below) |
| `docs/` | SRS, DFD, ER and state diagrams, architecture, phases, decision records, results |
| `testing/` | Selenium IDE suite, JMeter plan, test case table |
| `report/` | Experiment 9 report |

## Setup

Needs Python 3.10+ and Node.js 20+.

```powershell
# Backend
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m alembic upgrade head     # creates the database tables
.venv\Scripts\python -m app.seed                 # users, satellites, demo alerts

# Web
cd ..\web
npm install

# Dataset (about 86 MB, from the repo root)
cd ..
powershell -File scripts/get_data.ps1
```

On macOS/Linux use `.venv/bin/python` and `bash scripts/get_data.sh`.

### Training the detector (optional, for real data instead of demo placeholders)

```powershell
cd backend
.venv\Scripts\python -m pip install -r ..\ml\requirements.txt   # torch, scikit-learn, pandas
.venv\Scripts\python -m app.pipeline.import_dataset              # CHANNEL rows for every satellite
.venv\Scripts\python -m app.pipeline.train                       # one LSTM per channel; resumable, ~81 channels
.venv\Scripts\python -m app.evaluation.baseline --out ..\docs\results\phase2_baseline
.venv\Scripts\python -m app.evaluation.reports --out ..\docs\results\phase3_persistence_comparison
```

This takes a while on a laptop CPU (the Phase 1 spike benchmarked ~36s/channel; expect more if something else on the machine is competing for CPU). It's resumable — rerunning `app.pipeline.train` skips channels that already have weights.

## Run

Two terminals:

```powershell
cd backend; .venv\Scripts\python -m uvicorn app.main:app --port 8000 --reload
cd web; npm run dev          # http://localhost:3001
```

The browser only talks to port 3001; the web app forwards `/api/*` to the backend.

| Role | Email | Password |
|---|---|---|
| Analyst | analyst@orbitalsentinel.test | sentinel123 |
| Administrator | admin@orbitalsentinel.test | admin123 |
| Evaluator | evaluator@orbitalsentinel.test | evaluator123 |

### Pages

| Route | Who | What |
|---|---|---|
| `/login` | anyone | sign in |
| `/dashboard` | logged in | risk-ranked alert list, acknowledge, live updates (SSE) |
| `/satellites/[id]` | logged in | health panel: verdict, severity, attribution, telemetry chart with flagged ranges shaded |
| `/evaluation` | Evaluator, Administrator | accuracy metrics (once trained) and the detection log |
| `/admin` | Administrator | dataset import, models, per-satellite monitoring config, start/stop sessions |

The alerts shown before any session has run are **demo placeholders** from the seed script. Starting a session from `/admin` (needs a trained model, see above) replaces them with real detections from replayed telemetry.

## API (so far)

| Method | Path | Who | Result |
|---|---|---|---|
| POST | `/api/login` · `/api/logout` | anyone | session cookie |
| GET | `/api/me` | logged in | the current user |
| GET | `/api/satellites` | logged in | satellites with current risk and verdict |
| GET | `/api/satellites/{id}/health` · `/channels` · `/telemetry` | logged in | health panel data |
| GET | `/api/alerts` | logged in | risk-ranked alert list |
| POST | `/api/alerts/{id}/acknowledge` | Analyst, Administrator | the updated alert, or 404 |
| GET | `/api/detections` | logged in | detection log, filterable/paginated |
| GET | `/api/ranking` | logged in | satellite risk ranking |
| GET | `/api/stream` | logged in | SSE: detection, alert.created, alert.updated, ranking |
| POST/DELETE/GET | `/api/sessions` | Administrator | start/stop/list monitoring sessions |
| GET/PUT | `/api/admin/config/{id}` | Administrator | monitoring config (history kept) |
| POST | `/api/admin/datasets/import` | Administrator | import the dataset |
| GET | `/api/admin/models` | Administrator, Evaluator | trained models |
| GET | `/api/evaluation/metrics` | Evaluator, Administrator | accuracy, from the precomputed reports |
| GET/POST | `/api/reset` | dev only | restores the demo alerts (set `OS_ENABLE_TEST_RESET=false` to remove) |

## Tests

```powershell
cd backend; .venv\Scripts\python -m pytest -q; .venv\Scripts\python -m ruff check .
cd web; npx tsc --noEmit; npm run build
```

- **Selenium IDE:** open `testing/OrbitalSentinel.side` with both servers running.
- **JMeter:** `jmeter -n -t testing/OrbitalSentinel.jmx -l results.jtl` (targets port 3001; override with `-Jport=`).

## Dataset

`python -m app.pipeline.dataset` (from `backend/`) prints a summary. The release has 82 channel files, of which 81 are labelled (54 SMAP, 27 MSL). Two quirks are handled by the loader: `P-2` is listed twice in the labels (merged), and `T-10` has data but no labels (excluded from evaluation).
