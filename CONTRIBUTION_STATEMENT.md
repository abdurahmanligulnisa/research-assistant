# Contribution Statement

**Team:** _ExperimentMice_
**Topic:** Topic 4 — Async Research Assistant
**Repository:** [https://github.com/abdurahmanligulnisa/research-assistant](https://github.com/abdurahmanligulnisa/research-assistant)
**Final tag:** `v1.0-final`
**Submission date:** 2026-05-23

---

## Member A — Fidan Baghirova (`@Fidan6557`)

**Owned (sole author of these files / PRs):**
- `src/__init__.py`
- `src/config.py` — pydantic-settings typed configuration
- `src/models.py` — ResearchRequest, ResearchResult Pydantic models
- `src/logging_config.py` — structured logging setup
- `src/services/__init__.py`
- `src/services/ai_service.py` — retries + timeouts + logging wrapper
- `src/services/rate_limiter.py` — custom token-bucket rate limiter (per-source defaults)
- `src/concurrency/__init__.py`
- `src/concurrency/orchestrator.py` — asyncio.gather + Semaphore + graceful degradation
- `scripts/bench.py` — sequential vs concurrent benchmark
- `scripts/benchmark.py`
- `requirements.txt` — all dependencies pinned to ==version
- `.env.example` — updated with full variable list and Gemini default
- `.gitignore` — corrected, scoped LaTeX ignores to report/ only
- `README.md` — complete project documentation
- PRs: #1, #4, #7, #11, #14, #15

**Co-owned (paired or substantially edited):**
- `docs/architecture.md` (reviewed and expanded with Fatima)

**Reviewed (PRs reviewed and merged):**
- PRs: #3, #6, #9, #10, #16

**Approximate share of commits:** 35%

---

## Member B — Fatima Alibabayeva (`@FatimaAlibabayeva`)

**Owned (sole author of these files / PRs):**
- `src/storage/__init__.py`
- `src/storage/repository.py` — async PostgreSQL session persistence (psycopg3)
- `src/storage/cache_store.py` — in-process dict-backed TTL cache store
- `src/cli.py` — Click CLI (ask, history, --sources, --no-cache, --json-output)
- `docs/architecture.md` — architecture diagram and component overview
- `streamlit_app.py` — 967-line Streamlit web UI integrated with run_research()
- `assets/logo.jpeg`
- `artefacts/bench_results.txt` — live network benchmark (sequential vs concurrent)
- `artefacts/coverage_report.txt` — pytest --cov output (87% coverage)
- `artefacts/demo_offline_run.txt` — offline demo run output
- `artefacts/pytest_output.txt` — full pytest -v output (127 tests)
- `Dockerfile` — multi-stage build, non-root user, python:3.12-slim
- `docker-compose.yml` — app + PostgreSQL on port 8501
- `report/report.tex` — LaTeX source of the team report
- `report/report.pdf` — compiled report PDF
- `report/slides.pdf` — compiled presentation slides PDF
- PRs: #3, #6, #9, #10, #13, #16

**Co-owned (paired or substantially edited):**
- `docs/architecture.md` (with Fidan)

**Reviewed (PRs reviewed and merged):**
- PRs: #2, #5, #7, #8, #12, #15

**Approximate share of commits:** 32%

---

## Member C — Gulnisa Abdurahmanli (`@abdurahmanligulnisa`)

**Owned (sole author of these files / PRs):**
- `src/core/__init__.py`
- `src/core/researcher.py` — run_research() full pipeline orchestrator
- `researcher/__init__.py`
- `researcher/__main__.py` — python -m researcher entry point
- `src/services/cache.py` — TTL in-memory cache with --no-cache bypass
- `src/services/web_provider.py` — DuckDuckGo / Tavily / Serper adapters
- `tests/conftest.py` — FakeLLM, FakeWebSearch, no_real_ai autouse, clear_cache autouse
- `tests/test_ai_smoke.py` — provided smoke tests (verified not modified)
- `tests/test_cache.py`
- `tests/test_cli.py`
- `tests/test_concurrency.py`
- `tests/test_researcher.py`
- `tests/test_service.py`
- `tests/test_models.py`
- `tests/test_storage.py`
- `tests/test_http_mocking.py`
- `tests/test_logging_config.py`
- `tests/test_repository.py`
- `tests/test_web_provider.py`
- `pytest.ini` — updated test configuration (asyncio auto mode)
- `.github/workflows/ci.yml` — GitHub Actions CI (ruff, mypy, pytest, docker build)
- `.github/pull_request_template.md` — PR hygiene template
- `CONTRIBUTION_STATEMENT.md`
- PRs: #2, #5, #8, #12

**Co-owned (paired or substantially edited):**
- `docker-compose.yml` (reviewed with Fatima)

**Reviewed (PRs reviewed and merged):**
- PRs: #1, #3, #4, #6, #7, #9, #10, #11, #13, #14, #16

**Approximate share of commits:** 33%

---

## AI tool disclosure

We used AI coding assistants as follows:

| Module / file | Assistant | What we did with it |
|---|---|---|
| `streamlit_app.py` | Claude | Generated initial UI layout; team integrated run_research() pipeline, added session history, source toggles, and --no-cache support. |
| `Dockerfile` | Claude | Suggested multi-stage build pattern; team adapted for non-root user, venv isolation, and correct CMD for offline demo. |

We affirm that we **can defend every line of code** in this repository during the oral defense. "The AI wrote it" is not an answer we will use.

---

## Signatures

By signing below, we affirm that:
- The contributions described above are accurate.
- The commit percentages reflect actual work, not artificially split commits.
- Every line of code in the repository can be defended by at least one team member.
- AI assistant usage has been disclosed as described above.

| Member | Signature | Date |
|---|---|---|
| Fidan Baghirova | __________________________ | 2026-05-23 |
| Fatima Alibabayeva | __________________________ | 2026-05-23 |
| Gulnisa Abdurahmanli | __________________________ | 2026-05-23 |