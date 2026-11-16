# SmartShopper

AI shopping intelligence platform — understands shoppers, ranks real catalogue
products with explainable scores, and lets users experiment with preferences in
**Decision Lab**.

> Phase 2 status: user profiles, Shopper DNA, shopping history, and a demo
> product catalogue are implemented with migrations, seeding, and API tests.
> Recommendation scoring, Decision Lab, and Groq arrive in later phases.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React, Vite, TypeScript, Tailwind CSS, Lucide, Recharts |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Pydantic, Alembic |
| Database | SQLite (local development) |
| AI (later) | Groq API via server-side env vars |

## Repository layout

```
smartshopper/
├── frontend/     # Vite + React UI
├── backend/      # FastAPI API + Alembic
├── docs/         # Architecture notes
├── .env.example
└── README.md
```

## Prerequisites

- Node.js 20+ (Node 24 tested)
- Python 3.11+
- macOS / Apple Silicon supported

## Setup

### 1. Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Seed the **demo/mock** catalogue (idempotent — safe to re-run):

```bash
cd backend
source .venv/bin/activate
python -m app.data.seed_cli
```

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Dev requests to `/api`
are proxied to the backend.

## Tests

```bash
cd backend
source .venv/bin/activate
pytest
```

```bash
cd frontend
npm run build
```

## Environment variables

See `.env.example`, `backend/.env.example`, and `frontend/.env.example`.
`GROQ_API_KEY` is reserved for Phase 6 and must never be exposed to the browser.

## Design direction

**Quiet Commerce** — ivory / navy / sage, generous whitespace, editorial product
focus. Full navigation and feature screens ship when their backends exist.

## Phase roadmap

1. **Foundation** (this phase)
2. Database models, profiles, Shopper DNA
3. Product catalogue
4. Recommendation engine
5. Decision Lab
6. Groq AI assistant
7. Frontend feature screens + integration
8. Insights, testing, polish
9. Security, docs, GitHub, deployment
