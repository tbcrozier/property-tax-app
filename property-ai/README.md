# Property-AI

AI-powered property tax analysis for Davidson County, Nashville TN.

Ask questions in plain English. The system searches the knowledge base, runs iterative database queries, and returns a data-grounded answer — all through a single chat endpoint. It continuously improves itself based on the quality of its own responses.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI (Python 3.12, async) |
| Database | PostgreSQL + PostGIS + pgvector |
| LLM + Embeddings | Ollama (local, `qwen2.5-coder:7b` + `nomic-embed-text`) |
| ORM | SQLAlchemy 2.0 AsyncSession |
| Containerization | Docker Compose |

---

## Single Entry Point — How It Works

Everything flows through one endpoint:

```
POST /chat/  { "messages": [{"role": "user", "content": "..."}] }
```

You never need to know about the other endpoints. The system figures out what you need.

---

## Request Flow

```
User question
      │
      ▼
┌─────────────────────────────────────────────────────────┐
│  Step 1: INTENT CLASSIFICATION  (intent_router.py)      │
│                                                         │
│  Keyword scan — no LLM call:                           │
│    "report", "full analysis"  → REPORT                  │
│    everything else            → DATA                    │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│  Step 2: RAG — fetched once, passed into ReAct loop     │
│                                                         │
│  search_documents(top_k=10) — vector search             │
│  Returns top-10 most relevant chunks from:              │
│    nashville_zoning.md                                  │
│    valuation_anomaly_guide.md                           │
│    property_tax_glossary.md                             │
│    query_examples.md                                    │
│    flood_zones.md / us_zoning.md                        │
│                                                         │
│  identify_knowledge_gaps() — surfaces low-rated topics  │
│  (sequential calls — same DB session, no race condition) │
└──────────────────┬──────────────────────────────────────┘
                   │
          ┌────────┴────────┐
          │                 │
        DATA             REPORT
          │                 │
          ▼                 ▼
┌──────────────────┐  ┌─────────────────────────────────────┐
│ ReAct Loop       │  │ Bootstrap:                           │
│ (always runs,    │  │ detect_anomalies() always runs first │
│ no SQL fast path)│  │ IsolationForest on all parcels —     │
│                  │  │ LLM gets real data before writing    │
│ max_iterations=8 │  └──────────────┬──────────────────────┘
│ bootstrap=False  │                 │
└───────┬──────────┘                 ▼
        │                  ┌─────────────────────────────────┐
        └──────────────────► ReAct loop (non-streaming)      │
                           │ max_iterations=10               │
                           │                                 │
                           │  LLM drives the investigation:  │
                           │                                 │
                           │  Iter 1: search_docs            │
                           │    → understand domain context  │
                           │    (zoning codes, thresholds)   │
                           │                                 │
                           │  Iter 2: execute_sql            │
                           │    → SQL post-processing:       │
                           │      PERCENTILE_CONT removal    │
                           │      CTE alias fix              │
                           │      dead CTE stripping         │
                           │      column name normalization  │
                           │      fake table validation      │
                           │    → real rows returned         │
                           │                                 │
                           │  Iter 3: search_docs (optional) │
                           │    → interpret codes from       │
                           │      SQL results                │
                           │                                 │
                           │  Iter N: Final Answer           │
                           │    → grounded in all findings   │
                           │                                 │
                           │  Each tool result appended as   │
                           │  "Observation:" so LLM sees     │
                           │  full conversation history      │
                           └──────────────┬──────────────────┘
                                          │
                             ┌────────────┴────────────┐
                             │                         │
                        DATA path                 REPORT path
                             │                         │
                             │                   Saves .md to
                             │                   data/reports/
                             │                   SQL → saved_queries
                             │                   Findings →
                             │                   valuation_anomaly_guide.md
                             │                   Re-embedded immediately
                             │
                             ▼
         ┌─────────────────────────────────────────────────┐
         │  RAG-only fallback  (only if ReAct failed)      │
         │  system prompt = RAG chunks + parcel data       │
         │  LLM answers from knowledge docs alone          │
         └──────────────────┬──────────────────────────────┘
                            │
                            ▼  (background, does not block response)
         ┌─────────────────────────────────────────────────┐
         │  AUTO-EVAL (self-improvement)                   │
         │                                                 │
         │  Layer 1 — implicit signals:                    │
         │    SQL returned rows?      → +1.0               │
         │    SQL returned nothing?   → -1.0               │
         │    Answer is deflection    → -1.5               │
         │    Answer is detailed?     → +0.5               │
         │                                                 │
         │  Layer 2 — LLM grades its own answer:          │
         │    5 = answered with real data                  │
         │    2 = gave SQL instead of data                 │
         │    1 = didn't answer at all                     │
         │                                                 │
         │  effective_score = avg(layer1, layer2)          │
         │                                                 │
         │  score ≥ 4 → promote SQL in saved_queries      │
         │  score ≤ 2 → rewrite weak .md section          │
         │              re-embed into vector store         │
         └─────────────────────────────────────────────────┘
```

---

## ReAct Loop — How the LLM Investigates

The LLM is never handed pre-filtered data. It drives its own investigation using four tools, calling them in any order and as many times as needed within the iteration budget.

### Available Tools

| Tool | What it does |
|------|-------------|
| `execute_sql` | Writes and runs a SELECT query. Full post-processing pipeline applied before execution: PERCENTILE_CONT removal, dead CTE stripping, CTE alias leakage fix, column name normalization (30+ patterns), fake table validation |
| `search_docs` | Vector search over the knowledge base (top_k=6). Called before SQL to understand domain context, and after SQL to interpret raw codes |
| `detect_anomalies` | IsolationForest on up to 50k parcels using value_per_acre, acres, totl_appr, impr_appr, sale ratio. Returns top-N most anomalous parcels as a ranked table |
| `run_python` | Sandboxed Python execution on the last SQL result DataFrame. Used for custom aggregations |

### Good Investigation Pattern

```
1. search_docs  → understand zoning codes, valuation thresholds, domain rules
2. execute_sql  → query the database with informed filters
3. search_docs  → look up specific codes found in step 2 results (optional)
4. Final Answer → grounded in both data and domain knowledge
```

### How Each Question Type Flows

| Question | Tools called |
|----------|-------------|
| `"what is the assessed value of 123 Main St"` | `execute_sql` with ILIKE address match |
| `"tell me about parcel 04316019700"` | `execute_sql` joining parcels + parcel_signals |
| `"show miszoned properties and why"` | `search_docs` (zoning) → `execute_sql` (mismatch_reason CASE) |
| `"find anomalous commercial properties"` | `detect_anomalies` → `execute_sql` follow-up |
| `"top 20 appeal candidates in 37206"` | `search_docs` (thresholds) → `execute_sql` (parcel_signals) |
| `"generate a full report on over-assessed properties"` | bootstrap detect_anomalies → all tools → .md saved |

---

## Intent: DATA (default for all non-report questions)

Every question goes through the same ReAct loop. There is no separate fast path.

| Outcome | What happens |
|---------|-------------|
| **ReAct produces Final Answer** | Returned directly — LLM drove the full investigation |
| **ReAct fails or produces nothing** | RAG-only fallback — answer from knowledge docs alone |

---

## Intent: REPORT

Triggered by: "report", "full analysis", "deep analysis", "deep dive", "generate report", etc.

| Step | What happens |
|------|-------------|
| **Bootstrap** | `detect_anomalies()` always runs first — IsolationForest gives LLM real data before it writes anything |
| **ReAct loop** | Up to 10 iterations of all four tools |
| **Save report** | Full markdown saved to `data/reports/` |
| **Feed back** | SQL queries (only those that returned rows) → `saved_queries` table; findings distilled by LLM → `valuation_anomaly_guide.md` re-embedded |

---

## Self-Improvement Loop

```
Every response
    │
    ├── auto_eval scores quality (implicit + LLM self-grade)
    │
    ├── Good score (≥ 4)
    │       SQL promoted in saved_queries
    │       → pulled as few-shot example for similar future questions
    │
    └── Bad score (≤ 2)
            knowledge_service finds weak topic
            LLM rewrites that section of the .md file
            re-embedded into vector store immediately
            → RAG retrieves better context next time

Every report generated
    │
    ├── detect_anomalies bootstraps with real IsolationForest data
    │
    ├── SQL queries that returned rows → saved_queries
    │   (sql_idx tracks only row-returning calls to stay in sync
    │    with sql_history — zero-row and failed queries excluded)
    │
    └── LLM distills findings → appended to valuation_anomaly_guide.md
            re-embedded immediately
```

Optional manual override: `POST /chat/{query_id}/feedback` with `{"rating": 1-5}`.

---

## Example Questions

| Question | What happens |
|----------|-------------|
| `"what is the assessed value for 4918 Yorktown Road Nashville TN 37211"` | ReAct → SQL with ILIKE address match → real rows |
| `"list top 10 over-assessed residential parcels in 37206"` | ReAct → search_docs for thresholds → SQL with parcel_signals filters |
| `"tell me about parcel 04316019700"` | ReAct → SQL + parcel_signals JOIN |
| `"find anomalous commercial properties"` | ReAct → detect_anomalies + multi-step SQL follow-up |
| `"show miszoned properties and explain why"` | ReAct → search_docs (zoning) → SQL with lu_code/zoning CASE → explanation |
| `"explain what appeal score means"` | ReAct → search_docs only → RAG-based answer |
| `"generate a full report on zoning mismatches"` | REPORT → detect_anomalies bootstrap → ReAct loop → .md saved → learnings fed back |

---

## Project Structure

```
property-ai/
├── app/
│   ├── main.py                      # FastAPI app, startup signals
│   ├── db.py                        # Async engine, session factory
│   ├── config.py                    # Settings from .env
│   ├── cli.py                       # CLI: load-csvs, embed-docs, compute-signals
│   ├── models.py                    # ORM models (all tables)
│   ├── schemas.py                   # Pydantic request/response models
│   ├── llm.py                       # Ollama client wrapper
│   │
│   ├── services/
│   │   ├── intent_router.py         # Keyword-based: DATA (default) | REPORT
│   │   ├── chat_service.py          # Entry point: RAG → ReAct loop → fallback
│   │   ├── sql_service.py           # SQL post-processing pipeline + _COL_FIXES (authoritative)
│   │   ├── embed_service.py         # Chunking, embeddings, vector search
│   │   ├── parcel_service.py        # Comprehensive parcel analysis
│   │   ├── analyst_service.py       # ReAct tools: execute_sql, detect_anomalies, run_python, search_docs
│   │   ├── report_service.py        # _run_analyst_non_streaming + report generation + learnings
│   │   ├── auto_eval_service.py     # Implicit scoring + LLM self-evaluation
│   │   ├── knowledge_service.py     # Self-improving knowledge docs
│   │   ├── signals_service.py       # Pre-computed parcel_signals table
│   │   ├── loader_service.py        # Data ingestion from APIs + CSVs
│   │   └── analytics_service.py     # Query metrics, gap analysis
│   │
│   ├── routers/
│   │   ├── chat.py                  # POST /chat/ — main user entry point + auto-eval background task
│   │   ├── parcels.py               # GET /parcels/{id}/* — direct lookups
│   │   ├── analyst.py               # POST /analyst/ask|report|examples
│   │   ├── loader.py                # POST /loader/* — data loading
│   │   └── analytics.py            # GET /admin/* — system monitoring
│   │
│   └── static/
│       └── index.html               # Dark chat UI (Tailwind, Marked.js, Chart.js)
│
├── data/
│   ├── knowledge/                   # Markdown knowledge base (auto-improving)
│   │   ├── nashville_zoning.md
│   │   ├── valuation_anomaly_guide.md
│   │   ├── property_tax_glossary.md
│   │   ├── query_examples.md        # SQL examples — grows with good queries
│   │   ├── flood_zones.md
│   │   └── us_zoning.md
│   ├── reports/                     # Generated analysis reports (.md)
│   └── raw/                         # Source CSVs for initial data load
│
├── docker/
│   └── postgres/
│       ├── Dockerfile               # PostGIS + pgvector image
│       └── init.sql                 # Extensions: postgis, vector
│
├── docker-compose.yaml
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Database Tables

| Table | Description |
|-------|-------------|
| `parcels` | 285K+ Davidson County parcels with assessment values |
| `parcel_signals` | Pre-computed appeal scores, z-scores, recommendations — used by ReAct SQL queries instead of computing window functions |
| `building_permits` | Construction permits linked to parcels |
| `building_characteristics` | Finished area, structure type per parcel |
| `building_footprints` | Actual building footprints from aerial data |
| `flood_zones` | FEMA NFHL flood zone polygons |
| `cell_towers` | FCC-registered cell towers |
| `rail_lines` | BTS NARN railroad lines |
| `zoning_districts` | Metro Nashville zoning boundaries |
| `public_schools` | NCES public school locations |
| `school_performance` | Achievement scores, graduation rates |
| `correctional_facilities` | Jails, prisons, detention facilities |
| `crime_incidents` | MNPD crime incidents with location |
| `police_reporting_areas` | MNPD reporting area boundaries |
| `documents` | Knowledge base chunks with 768-dim embeddings |
| `saved_queries` | Growing library of rated question→SQL pairs |
| `query_feedback` | Every chat response with auto_score + manual rating |
| `query_metrics` | Aggregate performance by query pattern |

---

## API Endpoints

### User-facing

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/chat/` | Ask anything — main entry point |
| `POST` | `/chat/{id}/feedback` | Optional: manually rate a response (1-5) |

### Direct data access (programmatic / power users)

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/parcels/{par_id}` | Raw parcel record |
| `GET` | `/parcels/{par_id}/analysis` | Appeal score + comps |
| `GET` | `/parcels/{par_id}/comprehensive-analysis` | All data sources |
| `GET` | `/parcels/hit-list/search` | Top appeal candidates |
| `POST` | `/analyst/ask` | Streaming deep analysis |
| `POST` | `/analyst/report` | Non-streaming: saves .md report |
| `POST` | `/analyst/examples` | Seed query library manually |

### Admin / monitoring

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/admin/dashboard` | Query health metrics |
| `GET` | `/admin/knowledge-gaps` | Topics with low ratings |
| `GET` | `/admin/system-health` | Overall status |
| `POST` | `/admin/refresh-metrics` | Recalculate aggregates |

---

## Setup

### Prerequisites
- Docker Desktop
- Ollama running on host with models pulled:
  ```bash
  ollama pull nomic-embed-text
  ollama pull qwen2.5-coder:7b
  ```

### Start

```bash
cd property-ai
cp .env.example .env
docker compose up -d
```

App available at `http://localhost:8000`
Swagger UI at `http://localhost:8000/docs`
pgAdmin at `http://localhost:5050` (admin@admin.com / admin)

### Load data

```bash
# Load parcel CSV
docker compose exec app python -m app.cli load-csvs \
  --parcels data/raw/parcels.csv

# Load all API data sources
docker compose exec app python -m app.cli load-all

# Compute appeal signals
docker compose exec app python -m app.cli compute-signals

# Embed knowledge docs into vector store
docker compose exec app python -m app.cli embed-docs --docs-dir data/knowledge
```

### Environment variables (.env)

```env
DATABASE_URL=postgresql+asyncpg://property:property@db:5432/property_tax
DATABASE_URL_SYNC=postgresql+psycopg2://property:property@db:5432/property_tax
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_LLM_MODEL=qwen2.5-coder:7b
OLLAMA_EMBED_MODEL=nomic-embed-text
DEBUG=false
```
