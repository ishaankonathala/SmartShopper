# SmartShopper Architecture (Phase 1)

## Overview

SmartShopper is a monorepo with a React frontend and a FastAPI backend.
Recommendation scoring, Shopper DNA, Decision Lab, and Groq integration are
intentionally deferred to later phases.

## Runtime flow (Phase 1)

1. Vite serves the React app on `http://localhost:5173`.
2. The UI calls `GET /api/health`.
3. Vite proxies `/api` to FastAPI on `http://127.0.0.1:8000`.
4. FastAPI opens a SQLAlchemy session against SQLite and runs `SELECT 1`.
5. The health payload is returned to the UI.

## Design system

**Quiet Commerce** — warm ivory background, white surfaces, deep navy type,
muted sage accents, Manrope + Source Serif 4. Tokens live in
`frontend/src/index.css` (`@theme`).

## Phase 2 status

Domain tables (`user_profiles`, `shopper_dna`, `products`, `shopping_history`),
REST APIs, Alembic revision `20261116_0002`, and idempotent demo seeding are live.
See `docs/phase2-data-model.md`.

## Next phases

- Phase 3: deepen catalogue management / richer product APIs if needed
- Phase 4: deterministic recommendation engine
- Phase 5: Decision Lab counterfactual simulator
- Phase 6: Groq assistant with catalogue-grounded tool use
- Phase 7: full frontend screens wired to real APIs
- Phase 8: insights + broader tests
- Phase 9: hardening, docs, deployment
