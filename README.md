# Async Research Assistant — AIENG Final Project (Topic 4)

A software-engineering layer around an async AI research pipeline.
The system queries **Wikipedia**, **arXiv**, and a **web search API** in
parallel, then synthesizes a single cited answer using an LLM.

**Course:** AI-ENG-110 Software Engineering · **Team:** _ExperimentMice_  
**Due:** May 23, 2026 at 23:59 (UTC+4) · **Tag:** `v1.0-final`

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technologies Used](#2-technologies-used)
3. [Architecture Overview](#3-architecture-overview)
4. [Setup & Installation](#4-setup--installation)
5. [Environment Configuration](#5-environment-configuration)
6. [Running the Project](#6-running-the-project)
7. [Web UI (Streamlit)](#7-web-ui-streamlit)
8. [Database Initialization](#8-database-initialization)
9. [CLI Usage & Examples](#9-cli-usage--examples)
10. [Running Tests](#10-running-tests)
11. [Benchmark: Sequential vs Concurrent](#11-benchmark-sequential-vs-concurrent)
12. [Docker](#12-docker)
13. [Project Structure](#13-project-structure)
14. [Known Limitations](#14-known-limitations)

---

## 1. Project Overview

The user submits a research question. The system concurrently fetches sources
from three origins (Wikipedia, arXiv, web search), caches the results by a
canonicalized query key, deduplicates overlapping URLs, and calls an LLM to
produce a cited Markdown answer. Every AI call is wrapped with exponential
backoff retries, per-source timeouts, and graceful degradation — if one source
fails, the answer is still produced from the remaining ones.

---

## 2. Technologies Used

| Layer | Technology |
|---|---|
| Language | Python 3.12 (Docker) / Python 3.13 (local development tested) |
| AI / LLM | Anthropic Claude / OpenAI GPT-4o-mini / Google Gemini (pluggable) |
| Web search | DuckDuckGo (no key) · Tavily · Serper |
| Async HTTP | httpx |
| Concurrency | asyncio, asyncio.gather, asyncio.Semaphore, asyncio.to_thread |
| Retries | tenacity (exponential backoff) |
| Rate limiting | Request-rate token-bucket (`TokenBucketRateLimiter`) per source + LLM tokens-per-minute (`LlmTpmLimiter`) for synthesis |
| Validation | Pydantic v2 + pydantic-settings |
| CLI | Click |
| Web UI | Streamlit (bonus feature) |
| Database | PostgreSQL via psycopg3 (async, optional) |
| Testing | pytest + pytest-asyncio + pytest-cov + pytest-httpx + respx |
| Type checking | mypy |
| Linting | ruff |
| Containerization | Docker (multi-stage) + Docker Compose |
| CI | GitHub Actions |
---

## 3. Architecture Overview

```
User / CLI  ·  streamlit_app.py
    │  ResearchRequest  (validated Pydantic model)
    ▼
src/core/researcher.py              ← business logic orchestrator
    ├── cache lookup
    │       └── src/services/cache.py  ← TTL cache (source, query) → sources
    │               └── src/storage/cache_store.py  ← in-process dict-backed store
    │
    └── src/concurrency/orchestrator.py
            ├── asyncio.gather(wiki, arxiv, web)   ← parallel fetch
            ├── asyncio.Semaphore(MAX_CONCURRENT)  ← bounds parallelism
            ├── per-source asyncio.timeout()       ← fail-fast per source
            └── graceful degradation               ← failed sources excluded, answer still produced
                    │
            src/services/ai_service.py             ← retries + logging + timeout wrapper
                    ├── tenacity exponential backoff
                    └── src/services/rate_limiter.py  ← token-bucket (per-source defaults)
                    │
            src/services/web_provider.py           ← DuckDuckGo / Tavily / Serper
                    │
            ai/ module (PROVIDED — DO NOT MODIFY)
                    ├── fetch_wikipedia()
                    ├── fetch_arxiv()
                    ├── fetch_web()
                    └── synthesize()  ← offloaded via asyncio.to_thread
                    │
    ├── src/storage/repository.py    ← PostgreSQL session persistence (psycopg3)
    │       └── CREATE TABLE IF NOT EXISTS on init
    │
    └── ResearchResult  (Pydantic model returned to caller)
            │
    src/cli.py  ←  researcher ask / researcher history
```

Key design decisions:

- **Every** `ai.*` call goes through `AIService`. No direct `ai.*` imports in
  business logic.
- The cache stores raw `Source` objects keyed by `(source_name, canonicalized_query)`.
  A `--no-cache` flag bypasses both read and write.
- `ai.synthesize` is synchronous (LLM call). It is offloaded with
  `asyncio.to_thread` so the event loop is never blocked.
- All source-fetch failures are caught per-source; partial results are still
  synthesized. Failed source names are surfaced in `ResearchResult.sources_failed`.

---

## 4. Setup & Installation

### Prerequisites

- Python 3.12+
- PostgreSQL 14+ _(optional — only needed for `researcher history`)_
- Docker + Docker Compose _(optional — for containerized runs)_

### Install

```bash
# 1. Clone the repository
git clone https://github.com/abdurahmanligulnisa/research-assistant.git

cd research-assistant

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install pinned dependencies
pip install -r requirements.txt
```

---

## 5. Environment Configuration

```bash
# Copy the template and fill in your values
cp .env.example .env
```

Open `.env` and replace the placeholder values. **Required** before any live run:

| Variable | Required? | Description |
|---|---|---|
| `LLM_PROVIDER` | Yes | `anthropic` \| `openai` \| `gemini` |
| `LLM_MODEL` | Yes | e.g. `claude-sonnet-4-6`, `gpt-4o-mini`, `gemini-2.0-flash` |
| `ANTHROPIC_API_KEY` | If anthropic | Your Anthropic API key (`sk-ant-...`) |
| `OPENAI_API_KEY` | If openai | Your OpenAI API key (`sk-...`) |
| `GOOGLE_API_KEY` | If gemini | Your Google AI key (`AIza...`) |
| `WEB_SEARCH_PROVIDER` | No | `duckduckgo` (default, no key needed) \| `tavily` \| `serper` |
| `TAVILY_API_KEY` | If tavily | Tavily API key |
| `DATABASE_URL` | No | `postgresql://USER:PASS@HOST:5432/DBNAME` — omit to skip history |
| `MAX_CONCURRENT` | No | Semaphore bound (default `5`) |
| `CACHE_TTL_SECONDS` | No | Cache TTL in seconds; `0` = never expire (default `3600`) |

> **Tip**: DuckDuckGo works out of the box with no API key. Use it for the
> offline demo and testing.

---

## 6. Running the Project

### Offline demo (no API keys, no network)

```bash
# Provided demo harness — uses fake providers
python demo_ai.py --offline

# Your SE-layer demo — runs all 5 research questions
python scripts/demo.py --offline
python scripts/demo.py --offline --limit 5   # same, explicit
```

### CLI — live mode (requires `.env` with valid keys)

```bash
# Ask a research question (all three sources)
python -m researcher ask "What is photosynthesis?"

# Restrict to specific sources
python -m researcher ask "quantum computing basics" --sources wiki,arxiv

# Bypass the cache
python -m researcher ask "latest LLM research" --no-cache

# Machine-readable JSON output (for piping / scripts)
python -m researcher ask "CRISPR gene editing" --json-output

# View session history (requires DATABASE_URL to be set)
python -m researcher history --limit 10

# Adjust log verbosity
python -m researcher --log-level DEBUG ask "AI safety"
```

---

## 7. Web UI (Streamlit) Bonus

A browser-based interface for the research assistant — ask questions, view
cited answers, and browse session history, all without the CLI.

### Run locally

```bash
# Make sure .env is filled in with valid API keys
streamlit run streamlit_app.py
```

Then open: **http://localhost:8501**

### Run with Docker (single container, no history)

```bash
# Build the image first
docker build --platform linux/amd64 -t researcher .

# Run Streamlit (history disabled — no PostgreSQL)
docker run --env-file .env -p 8501:8501 researcher streamlit run streamlit_app.py --server.address=0.0.0.0
```

Then open: **http://localhost:8501**

> **Note:** In single-container mode, PostgreSQL is not available so
> `researcher history` is silently skipped. Use Docker Compose below
> for full history persistence.

### Run with Docker Compose (with PostgreSQL history)

This is the recommended way to run Streamlit — it starts both the app and
PostgreSQL together so history is fully persisted.

```bash
# 1. Copy and fill in .env (set API keys — DATABASE_URL is pre-configured in docker-compose.yml)
cp .env.example .env

# 2. Build and start both services (app + PostgreSQL)
docker compose up --build

# 3. Open the web UI
# http://localhost:8501
```

To run in the background:
```bash
docker compose up --build -d
docker compose logs -f app     # follow app logs
```

To run a one-off research question via Compose:
```bash
docker compose run app python -m researcher ask "What is quantum computing?"
```

To stop and clean up:
```bash
docker compose down            # stop containers, keep DB volume
docker compose down -v         # stop + delete DB volume (wipes history)
```

The Streamlit UI supports:
- Asking research questions with source selection (wiki / arxiv / web)
- `--no-cache` toggle for always-fresh results
- Viewing cited answers with numbered references
- Browsing session history — **persisted to PostgreSQL via Docker Compose**

> **Note:** `DATABASE_URL` inside the container points to the `db` service
> (`postgresql://...@db:5432/research`), not `localhost`. This is already
> configured in `docker-compose.yml` — do not change it to `localhost`.

---

## 8. Database Initialization

The database schema is created automatically on first use (`CREATE TABLE IF NOT EXISTS`).  
If you want to create it explicitly:

```bash
# From Python
python -c "
import asyncio
from src.storage.repository import init_db
asyncio.run(init_db())
print('Database initialized.')
"
```

**Table created:** `research_sessions`

```sql
CREATE TABLE IF NOT EXISTS research_sessions (
    id              SERIAL PRIMARY KEY,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    citations_json  JSONB NOT NULL DEFAULT '[]',
    sources_failed  JSONB NOT NULL DEFAULT '[]',
    cached          BOOLEAN NOT NULL DEFAULT FALSE,
    elapsed_seconds FLOAT NOT NULL DEFAULT 0.0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_research_sessions_created_at
    ON research_sessions (created_at DESC);
```

> **Note:** The `DATABASE_URL` variable must be set in `.env` for the
> repository to connect. If it is absent or wrong, all persistence calls
> are logged at WARNING level and the application continues without history.

---

## 9. CLI Usage & Examples

### `ask` command

```bash
python -m researcher ask QUESTION [OPTIONS]

Arguments:
  QUESTION   The research question (wrap in quotes if it contains spaces)

Options:
  --sources TEXT     Comma-separated subset: wiki,arxiv,web (default: all three)
  --no-cache         Bypass the TTL cache; always fetch fresh results
  --json-output      Print result as JSON instead of formatted text
  --log-level LEVEL  DEBUG | INFO | WARNING | ERROR  (default: INFO)
```

**Example output:**

```
Q: What is photosynthesis?

A: Photosynthesis is the process by which plants convert light energy into
chemical energy stored as glucose [1]. The two main stages are the
light-dependent reactions [1] and the Calvin cycle [2].

References:
  [1] (wikipedia) Photosynthesis
      https://en.wikipedia.org/wiki/Photosynthesis
  [2] (arxiv) Light-Dependent Reactions of Photosynthesis
      https://arxiv.org/abs/...

  [took 1.42s]
```

### `history` command

```bash
python -m researcher history [--limit N]

Options:
  --limit INTEGER   Number of recent sessions to display (default: 10)
```

---

## 10. Running Tests

```bash
# Full test suite with coverage
pytest --cov=src --cov-report=term-missing

# Smoke tests only (provided — MUST always pass)
pytest tests/test_ai_smoke.py -v

# Single test file
pytest tests/test_concurrency.py -v

# All tests — quiet output
pytest -q
```

**Coverage target:** ≥ 60% (actual: 87% as of v1.0-final).  
All tests are **fully offline** — AI module and HTTP layer are mocked.

---

## 11. Benchmark: Sequential vs Concurrent

### Offline simulation (no API keys required)

```bash
python scripts/benchmark.py --n 5 --offline
```

**Offline results (simulated latency):**

| Mode       | Time (s) | Speedup |
|------------|----------|---------|
| Sequential |    3.170 |   1.00x |
| Concurrent |    1.311 |   2.42x |

> N=5 questions × 3 sources, `max_concurrent=5` (semaphore), offline mode.  
> For real-network numbers, run without `--offline`.


### Real-network benchmark (spec-required)

To reproduce real-network numbers on your machine with caches cleared:

```bash
# 1. Fill in API keys
cp .env.example .env && $EDITOR .env   # set ANTHROPIC_API_KEY + TAVILY_API_KEY

# 2. Run the benchmark (caches are cleared automatically before each timed run)
python scripts/benchmark.py --n 5
```

**Benchmark results (live network, Tavily web provider):**

| Mode       | Time (s) | Speedup |
|------------|----------|---------|
| Sequential |   45.513 |  1.00x  |
| Concurrent |    5.158 | **8.82x** |

N=5, max_concurrent=5 (semaphore), mode=live  
To reproduce: `python scripts/benchmark.py --n 5`

**Why the speedup?** Source fetches are I/O-bound. `asyncio.gather(wiki, arxiv, web)`
runs all three simultaneously so wall-clock time ≈ max(wiki, arXiv, web)
instead of their sum. A `Semaphore(MAX_CONCURRENT)` prevents unbounded
concurrency and rate-protects external APIs. The 8.82× speedup reflects the
theoretical max-of-three vs. sum-of-three wall-clock model; further speedup
is bottlenecked by LLM synthesis time and network variance, not the
concurrency implementation.

---

## 12. Docker

### Multi-stage build

The Dockerfile uses a **two-stage build** for a minimal, secure production image:

- **Builder stage** — installs all dependencies into an isolated virtual environment (`/venv`)
- **Runtime stage** — copies only `/venv` into a clean `python:3.12-slim` base image
- Runs as a **non-root user** (`appuser`) for container security
- Final image contains no build tools, compilers, or pip cache — significantly smaller than a single-stage build

```bash
# Build
docker build --platform linux/amd64 -t researcher .

# Inspect final image size
docker images researcher
```

> **Expected image size:** ~220 MB (multi-stage build — runtime stage only,
> no build tools or pip cache). Run `docker images researcher` after building
> to confirm on your machine.

### Build & run (offline demo)

```bash
docker build --platform linux/amd64 -t researcher .
docker run researcher                          # offline demo (default CMD)
```

### Run with real providers

```bash
# Make sure .env is filled in
docker run --env-file .env researcher python -m researcher ask "What is AI?"
```

### Run Streamlit (single container, no DB)

```bash
docker run --env-file .env -p 8501:8501 researcher streamlit run streamlit_app.py --server.address=0.0.0.0
```

Then open: **http://localhost:8501**

### Docker Compose (app + PostgreSQL + Streamlit)

```bash
# Copy and fill in .env first (especially POSTGRES_USER, POSTGRES_PASSWORD)
cp .env.example .env

docker compose up --build                      # starts db + app + streamlit
docker compose run app python scripts/demo.py --offline
docker compose down                            # stop, keep DB volume
docker compose down -v                         # stop + remove volumes (wipes history)
```

> **Replace** `POSTGRES_USER` and `POSTGRES_PASSWORD` in `.env` with
> strong credentials for any deployment beyond your local machine.

---

### Rate limiting

The project implements **two complementary rate limiters** in `src/services/rate_limiter.py`:

#### 1. Request-rate limiter (`TokenBucketRateLimiter`)

Controls how many *requests per second* each source may receive. Applied
automatically in `AIService` before every source fetch:

| Source    | Default rate |
|-----------|--------------|
| Wikipedia | 10 req/s     |
| arXiv     | 2 req/s      |
| Web       | 1 req/s      |

#### 2. LLM tokens-per-minute limiter (`LlmTpmLimiter`)

Controls LLM **prompt + completion token consumption** against the provider's
documented TPM ceiling. Applied automatically in `AIService.synthesize` after
every successful synthesis call, using the actual token counts from the
provider's usage metadata (falls back to `max_tokens` when usage data is
unavailable).

| Provider default                      | TPM limit |
|---------------------------------------|-----------|
| Anthropic claude-sonnet-4 (free tier) | 40 000    |
| OpenAI gpt-4o-mini                    | 200 000   |
| Google Gemini 2.0 Flash               | 1 000 000 |

This is a **different dimension** from the request-rate limiter: a single
synthesis call that produces 800 completion tokens consumes the same TPM quota
as eight 100-token calls. Only TPM tracking can prevent `429 RateLimitError`
responses from the LLM provider under heavy load.

Both limiters raise `RateLimitExceeded`, which integrates with the `tenacity`
retry loop in `AIService` — calls are automatically retried with exponential
backoff. Construct custom instances:

```python
from src.services.rate_limiter import TokenBucketRateLimiter, LlmTpmLimiter

# Source request-rate limiter
req_limiter = TokenBucketRateLimiter(rate=5.0, capacity=10)  # 5 req/s, burst of 10

# LLM TPM limiter (e.g. for a paid Anthropic tier at 200 000 TPM)
tpm_limiter = LlmTpmLimiter(tpm_limit=200_000)
```

---

## 13. Project Structure

```
research-assistant/
├── ai/                         ← PROVIDED by course (DO NOT MODIFY)
│   ├── __init__.py             ← public API: fetch_*, synthesize, schemas
│   ├── providers/              ← LLM provider adapters (Anthropic / OpenAI / Gemini)
│   ├── schemas.py              ← Source, Citation, AnswerWithCitations
│   ├── sources.py              ← fetch_wikipedia, fetch_arxiv, fetch_web
│   └── synthesizer.py         ← synthesize()
│
├── src/
│   ├── __init__.py             ← package init
│   ├── config.py               ← pydantic-settings (reads .env)
│   ├── models.py               ← SE-layer Pydantic models
│   ├── logging_config.py       ← structured logging setup
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ai_service.py       ← retries + timeouts + logging wrapper
│   │   ├── cache.py            ← TTL in-memory cache (source, query) → sources
│   │   ├── rate_limiter.py     ← request-rate limiter (per-source) + LLM TPM limiter
│   │   └── web_provider.py     ← DuckDuckGo / Tavily / Serper adapters
│   ├── core/
│   │   ├── __init__.py
│   │   └── researcher.py       ← run_research() — full pipeline
│   ├── concurrency/
│   │   ├── __init__.py
│   │   └── orchestrator.py     ← asyncio.gather + Semaphore + graceful degradation
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── repository.py       ← PostgreSQL session persistence (psycopg3)
│   │   └── cache_store.py      ← in-process TTL cache store
│   └── cli.py                  ← Click CLI (ask, history)
│
├── researcher/
│   ├── __init__.py
│   └── __main__.py             ← entry point: python -m researcher
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py             ← FakeLLM, FakeWebSearch, no_real_ai autouse, clear_cache autouse
│   ├── test_ai_smoke.py        ← PROVIDED — must not be deleted or weakened
│   ├── test_service.py         ← AIService tests (offline)
│   ├── test_cache.py           ← cache TTL, canonicalization, expiry
│   ├── test_concurrency.py     ← pipeline, semaphore, graceful degradation
│   ├── test_researcher.py      ← end-to-end pipeline (offline)
│   ├── test_cli.py             ← Click CliRunner tests
│   ├── test_models.py          ← Pydantic validation edge cases
│   ├── test_storage.py         ← repository save/retrieve/error paths
│   ├── test_http_mocking.py    ← pytest-httpx / respx HTTP mocking
│   ├── test_logging_config.py  ← logging setup tests
│   ├── test_repository.py      ← PostgreSQL repository (mocked)
│   └── test_web_provider.py    ← web provider adapter tests
│
├── scripts/
│   ├── demo.py                 ← end-to-end scripted demo (all 5 questions)                
│   └── benchmark.py            ← sequential vs concurrent benchmark
│
├── data/
│   └── research_questions.json ← 5 sample questions for demo & benchmark
│
├── artefacts/                  ← sample run outputs (required for submission)
│   ├── benchmark_results.txt       ← sequential vs concurrent timing
│   ├── coverage_report.txt     ← pytest --cov output
│   ├── demo_offline_run.txt    ← offline demo run output
│   └── pytest_output.txt       ← full pytest -v output
│
├── docs/
│   └── architecture.md         ← architecture diagram
│
├── report/
│   ├── report.tex              ← team report (fill in names, compile to PDF)
│   └── slides.tex              ← presentation slides
│
├── .github/
│   ├── workflows/
│   │   └── ci.yml              ← GitHub Actions CI (+2 bonus)
│   └── pull_request_template.md ← PR template
│
├── assets/
│   └── logo.jpeg               ← Streamlit web UI logo
│
├── streamlit_app.py            ← Streamlit web UI (+1 bonus)
├── Dockerfile                  ← multi-stage build (+1 bonus)
├── docker-compose.yml          ← app + PostgreSQL
├── requirements.txt            ← ALL deps pinned to ==version
├── requirements-ai.txt         ← AI module dependencies
├── .env.example                ← copy to .env, fill in keys
├── .gitignore
├── pytest.ini
├── demo_ai.py                  ← PROVIDED offline demo harness
├── CONTRIBUTION_STATEMENT.md   ← fill in, sign, submit
└── README.md
```
---

## 14. Known Limitations

- **In-process cache is ephemeral by design.** `src/services/cache.py`
  uses a plain Python dict as its backing store. The cache is **wiped on
  every process restart** — running `python -m researcher ask` as a one-shot
  CLI command always starts cold. It is also **not shared** between processes;
  running multiple workers behind a load balancer gives each worker its own
  isolated cache instance. If persistence or cross-process sharing matters,
  replace the `_store` dict with a Redis or filesystem JSON backend — the
  `get`/`set`/`clear` API is intentionally minimal to make that swap easy.

- **Research history is persisted to PostgreSQL.** `src/storage/repository.py`
  saves every completed `ResearchResult` to the database. History is silently
  skipped if `DATABASE_URL` is not set or the database is unreachable — the
  application degrades gracefully. Use the provided Docker Compose setup for
  a zero-config local PostgreSQL: `docker compose up -d`.

- **Connection pool is bounded to 5 connections.**
  `psycopg_pool.AsyncConnectionPool` caps simultaneous DB connections at
  `max_size=5` (configurable via env). Under very heavy concurrent load,
  excess requests will queue inside the pool.

- **Two rate limiters with different scopes.**
  `src/services/rate_limiter.py` provides two distinct limiters.
  `TokenBucketRateLimiter` controls *request frequency* per source
  (Wikipedia: 10 req/s, arXiv: 2 req/s, web: 1 req/s) and is applied
  automatically in `AIService` before every fetch.
  `LlmTpmLimiter` controls *LLM token consumption* against the provider's
  tokens-per-minute ceiling and is applied automatically in
  `AIService.synthesize` using actual prompt + completion token counts from
  the provider response. Both are single-process; a Redis backend would be
  needed for multi-worker coordination.

- **DuckDuckGo is rate-limited.**
  Under burst traffic it can return empty results or raise
  `RatelimitException`. Use Tavily or Serper for reliable production
  web search (`WEB_SEARCH_PROVIDER=tavily` in `.env`).

- **SQLite is not supported.**
  The repository uses psycopg3 SQL syntax (`%s` placeholders, `JSONB`,
  `SERIAL`, `TIMESTAMPTZ`) which is PostgreSQL-specific. Use the provided
  Docker Compose setup for a zero-config local PostgreSQL.

See `report/report.pdf` §8 for a full discussion of limitations and future work.