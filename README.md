# SmartShopper AI

**An agentic AI shopping assistant that understands shopper preferences, searches product catalogues, compares options, and provides grounded, explainable recommendations.**

SmartShopper AI helps users make better shopping decisions through conversational interaction, structured product discovery, preference-aware recommendations, and transparent comparisons.

Instead of relying on an LLM to invent product suggestions, SmartShopper combines bounded AI agent orchestration with deterministic catalogue search, recommendation, comparison, and evaluation tools.

---

## Key Features

### 1. Agentic AI Shopping Assistant
- Conversational shopping experience powered by Groq.
- Structured planning that selects from an allowlisted set of tools.
- Bounded multi-step orchestration with request-scoped state.
- Context-aware follow-up questions.
- Deterministic fallback when AI planning is unavailable.
- Agent activity timeline showing the tools and actions used.

### 2. Product Discovery
- Discover products from a separate Amazon Electronics catalogue.
- Browse products across multiple electronics categories.
- View product details, ratings, images, and available catalogue information.
- Recently viewed product tracking.

### 3. Intelligent Recommendations
- Preference-aware product ranking.
- Budget and category-aware recommendations.
- Explainable recommendation scores and reasons.
- Grounded recommendations based on available catalogue data.
- Evaluation checks to prevent unsupported or incomplete recommendations.

### 4. Product Comparison
- Compare products using available structured attributes.
- Contextual comparisons based on the current conversation.
- Clear disclosure when product information is unavailable.

### 5. Shopper Profile and Preferences
- Shopper DNA and preference controls.
- Budget and category preferences.
- Brand preferences and disliked attributes.
- Persistent shopping preferences.

### 6. Wishlist and Shopping History
- Save and remove products from a wishlist.
- Access saved products in one place.
- Track shopping activity and recently viewed products.
- Persist relevant frontend state locally.

---

## Technology Stack

| Layer | Technologies |
|---|---|
| Frontend | React 19, TypeScript, Vite, Tailwind CSS |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Pydantic |
| Database | SQLite, Alembic |
| AI / LLM | Groq API |
| Data Processing | Pandas, PyArrow |
| Testing | Pytest |
| UI Icons | Lucide React |

---

## Architecture

SmartShopper uses a hybrid architecture combining LLM-based planning with deterministic execution.

### Agent workflow

1. **User request:** The user describes a shopping requirement in natural language.
2. **Planning:** The planner interprets the request and selects appropriate actions.
3. **Tool execution:** The orchestrator executes validated actions using registered tools.
4. **Grounded results:** Tools retrieve and process actual catalogue and preference data.
5. **Evaluation:** Recommendations are checked before being presented.
6. **Response:** The assistant explains the results using available product information.

### Agent tools

The agent includes tools for:

- Product search
- Shopper profile retrieval
- Preference simulation
- Product comparison
- Recommendation evaluation

The orchestration is deliberately bounded, with a maximum of five tool executions and three planning iterations per request. Tool access is restricted through an allowlisted registry and validated schemas.

The LLM assists with planning and explanations; catalogue retrieval, ranking, and evaluation remain grounded in application data.

---

## Repository Structure

```text
SmartShopper/
├── backend/
│   ├── app/
│   │   ├── agent/
│   │   │   ├── tools/
│   │   │   ├── orchestrator.py
│   │   │   ├── planner.py
│   │   │   ├── schemas.py
│   │   │   └── state.py
│   │   ├── api/
│   │   ├── data/
│   │   ├── models/
│   │   ├── schemas/
│   │   └── services/
│   ├── alembic/
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── hooks/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── services/
│   │   └── types/
│   └── .env.example
├── docs/
├── .env.example
├── .gitignore
└── README.md
```

---

## Getting Started

### Prerequisites

- Python 3.11 or newer
- Node.js 20 or newer
- npm
- Git

### 1. Clone the repository

```bash
git clone https://github.com/ishaankonathala/SmartShopper.git
cd SmartShopper
```

### 2. Set up the backend

```bash
cd backend

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env

alembic upgrade head
```

Start the backend:

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend health check:

http://127.0.0.1:8000/api/health

Interactive API documentation:

http://127.0.0.1:8000/docs

### 3. Seed the demo catalogue

In a separate terminal:

```bash
cd backend
source .venv/bin/activate

python -m app.data.seed_cli
```

The seed command populates the curated demo catalogue used by the recommendation system.

### 4. Set up the frontend

In a separate terminal:

```bash
cd frontend

npm install
cp .env.example .env

npm run dev
```

Open:

http://localhost:5173

The Vite development server proxies `/api` requests to the backend.

---

## Amazon Electronics Catalogue

SmartShopper maintains a separate Amazon Electronics catalogue for product discovery.

The dataset is based on the **Amazon Reviews 2023** project:

https://amazon-reviews-2023.github.io/

The imported catalogue is separate from the curated demo products used by the recommendation engine.

### Dataset setup

The original Parquet dataset is intentionally excluded from GitHub because of its large file size.

For local catalogue import, obtain the required source shard and place it at:

```text
backend/app/data/full-00000-of-00010.parquet
```

Run a dry-run preview:

```bash
cd backend
source .venv/bin/activate

python -m app.data.amazon_import_cli --dry-run
```

Apply database migrations:

```bash
alembic upgrade head
```

Import the selected products:

```bash
python -m app.data.amazon_import_cli
```

The importer supports:

- `--dry-run`
- `--limit`
- `--usd-to-inr`
- `--source`

The importer is designed to be idempotent and does not insert Amazon catalogue products into the curated recommendation table.

### Important catalogue limitations

- Catalogue prices are historical source values, not current Indian retail prices.
- USD prices are converted using an illustrative fixed conversion rate of ₹85 per USD by default.
- Product availability and live retailer inventory are not verified.
- Catalogue data should not be interpreted as real-time market pricing.

---

## Testing and Validation

### Backend tests

```bash
cd backend
source .venv/bin/activate

pytest
```

The latest reported backend test run completed with **462 passing tests**.

### Frontend build

```bash
cd frontend

npm run build
```

Frontend linting:

```bash
npm run lint
```

---

## Environment Configuration

Environment examples are provided in:

- `.env.example`
- `backend/.env.example`
- `frontend/.env.example`

Copy the relevant example into a local `.env` file before running the corresponding application.

Keep API keys and secrets on the backend. Never expose the Groq API key in frontend code or commit real `.env` files to GitHub.

---

## Design Philosophy

**Quiet Commerce**

SmartShopper follows a clean, editorial shopping interface built around:

- Warm ivory backgrounds
- Deep navy typography
- Muted sage accents
- Generous whitespace
- Clear product presentation
- Explainable recommendations

The interface prioritizes decision-making and product clarity rather than overwhelming users with information.

---

## Project Status

The core application includes:

- Agentic shopping assistant and bounded tool orchestration
- Grounded product search and recommendation workflows
- Amazon Electronics catalogue discovery
- Product details and comparisons
- Shopper preferences and profile controls
- Wishlist and shopping history
- Backend API and automated test coverage

---

## Future Improvements

Potential extensions include:

- Live retailer catalogue integrations
- Real-time inventory and price tracking
- More product categories and catalogue sources
- Advanced recommendation evaluation
- Additional agent tools and shopping workflows
- Deployment and production monitoring

---

## Author

**SmartShopper AI**
Developed as an AI/ML project using agent orchestration, LLMs, recommendation systems, and full-stack application development.