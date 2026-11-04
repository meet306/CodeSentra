# CodeSentra: Advanced AI-Powered GitHub PR Code Reviewer

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-Multi--Agent-purple.svg)](https://langchain-ai.github.io/langgraph/)
[![Groq](https://img.shields.io/badge/Groq%20API-Free%20Tier-orange.svg)](https://groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://img.shields.io/badge/CI-Passing-brightgreen.svg)]()

**CodeSentra** is an enterprise-grade, event-driven GitHub Pull Request Code Review System built entirely using free and open-source technologies, architected specifically for low resource consumption (optimized for 8 GB RAM machines) and 100% free-tier AI inference with the Groq API.

---

## Architecture Overview

```
GitHub Pull Request Event (opened / synchronize)
       │
       ▼
[ Gateway Service ]  ──► HMAC SHA-256 Signature Verification (X-Hub-Signature-256)
       │
       ▼
[ Webhook Processor ] ──► Idempotency Check & Delivery De-duplication
       │
       ├─► (Async Queue) Celery Worker + Redis
       │
       ▼
[ LangGraph Orchestrator ]
       │
       ├──► 1. Static Analysis Agent   (Bugs, logic errors, resource leaks)
       ├──► 2. Security Agent          (OWASP Top 10, Injection, Secrets)
       ├──► 3. Architecture Agent      (Coupling, design patterns, contracts)
       └──► 4. Code Style Agent        (Readability, complexity, learned rules)
       │
       ▼
[ Finding Merger ] ──► Cross-agent deduplication, severity ranking (CRITICAL -> INFO)
       │
       ▼
[ Reviewer Service ] ──► Posts structured markdown & inline comments (DRY_RUN supported)
       │
       ▼
[ PostgreSQL / SQLite ] ──► Review sessions, findings, comments, and audit logs
       ▲
       │
[ Learner Service ] ◄── Merged PRs -> Learn repository-specific conventions
```

---

## Multi-Agent Review Specialization

1. **Static Analysis Agent** (`app/agents/static_agent.py`):
   - Logic errors, off-by-one bugs, null attribute exceptions.
   - Resource leaks (unclosed sockets/files/connections).
   - Inefficient implementations and infinite loop risks.
2. **Security Agent** (`app/agents/security_agent.py`):
   - OWASP Top 10 risks (SQLi, Command Injection, SSRF, Path Traversal).
   - Hardcoded secrets, keys, and tokens.
   - Insecure authentication, authorization, and broken cryptography.
3. **Architecture Agent** (`app/agents/architecture_agent.py`):
   - Separation of concerns and modular boundary violations.
   - Circular dependencies and tight coupling.
   - Public API breaking changes and design pattern anti-patterns.
4. **Code Style Agent** (`app/agents/style_agent.py`):
   - Naming conventions and language idioms (PEP 8, camelCase).
   - Cyclomatic complexity and excessive nesting.
   - Enforcing repository-specific conventions discovered by the Learner Service.

---

## Free-Tier Constraints & Safety Features

- **Zero Paid Dependencies**: 100% free stack (Groq Free Tier, PostgreSQL OSS, Redis OSS, Prometheus/Grafana OSS).
- **Prompt Injection Defense**: Untrusted PR code and commit metadata are isolated within defensive XML delimiters (`<untrusted_diff>`, `<pr_context>`).
- **Diff & Memory Protection**: Automatic diff truncation (`MAX_DIFF_LINES=1200`) protects Groq free-tier token allowances and system memory.
- **Rate Limit Resilience**: Automatic exponential backoff retries when encountering Groq `429` rate limits.
- **Dry-Run Safety**: `DRY_RUN=true` by default prevents unintended comments from being posted to GitHub during testing.
- **Automatic Fallback Database**: Runs out-of-the-box with local SQLite (`aiosqlite`) if PostgreSQL is not launched.

---

## Directory Structure

```
CodeSentra/
├── app/
│   ├── main.py                     # FastAPI app factory, lifespan, routes
│   ├── config.py                   # Pydantic Settings & environment
│   ├── api/
│   │   ├── dependencies.py         # FastAPI dependency injection providers
│   │   └── routes/
│   │       ├── health.py           # Health check endpoints
│   │       ├── review.py           # On-demand PR review endpoints
│   │       ├── webhook.py          # GitHub webhook receiver
│   │       └── feedback.py         # Developer feedback intake
│   ├── core/
│   │   ├── errors.py               # Custom domain exceptions
│   │   ├── logging.py              # Secret-redacting logger
│   │   ├── metrics.py              # Prometheus metrics exporter
│   │   └── telemetry.py            # Langfuse telemetry tracer
│   ├── database/
│   │   ├── base.py                 # DeclarativeBase & UUID/Timestamp mixins
│   │   ├── session.py              # Async database engine & session maker
│   │   └── models/                 # 12 SQLAlchemy ORM models
│   ├── integrations/
│   │   ├── github.py               # GitHub REST API client
│   │   ├── github_app.py           # GitHub App RS256 JWT & token minting
│   │   └── groq.py                 # Groq client with backoff & schema parsing
│   ├── agents/                     # 4 Specialized Review Agents
│   │   ├── base.py
│   │   ├── static_agent.py
│   │   ├── security_agent.py
│   │   ├── architecture_agent.py
│   │   └── style_agent.py
│   ├── graph/                      # LangGraph Multi-Agent Workflow
│   │   ├── state.py
│   │   ├── nodes.py
│   │   └── workflow.py
│   ├── services/
│   │   ├── gateway/                # HMAC SHA-256 verification
│   │   ├── webhook/                # Webhook event processing & idempotency
│   │   ├── orchestrator/           # LangGraph workflow orchestration & merger
│   │   ├── reviewer/               # Markdown formatter & GitHub poster
│   │   └── learner/                # Pattern learner & feedback tracking
│   ├── schemas/                    # Pydantic data schemas
│   └── workers/                    # Celery app & background tasks
├── monitoring/
│   ├── prometheus.yml              # Prometheus scrape configuration
│   └── grafana/                    # Pre-configured Grafana dashboards
├── tests/                          # 42 Automated unit and integration tests
├── .github/workflows/ci.yml        # GitHub Actions CI workflow
├── docker-compose.yml              # Multi-container orchestration
├── Dockerfile                      # Production slim image
├── .env.example                    # Environment variable template
├── requirements.txt
└── pyproject.toml
```

---

## Quickstart Guide

### 1. Prerequisites
- Python 3.11+ (or Docker Desktop)
- Free Groq API Key: [https://console.groq.com/keys](https://console.groq.com/keys)

### 2. Local Environment Configuration

Copy `.env.example` to `.env`:
```powershell
Copy-Item .env.example .env
```

Configure your free Groq API key:
```env
GROQ_API_KEY=gsk_your_free_groq_api_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GITHUB_TOKEN=optional_github_token_here
DRY_RUN=true
```

### 3. Running Locally (Without Docker)

Activate the virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

Run database initialization and start the FastAPI server:
```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

The application runs at:
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Prometheus Metrics**: [http://127.0.0.1:8000/metrics](http://127.0.0.1:8000/metrics)

---

### 4. Running with Docker Compose

To start the core stack (Backend, Celery, PostgreSQL, Redis):
```bash
docker compose up -d
```

To also start the optional monitoring stack (Prometheus & Grafana) when memory permits:
```bash
docker compose --profile monitoring up -d
```
- **Grafana Dashboard**: [http://localhost:3001](http://localhost:3001) (User: `admin`, Password: `admin`)
- **Prometheus UI**: [http://localhost:9090](http://localhost:9090)

---

## API Endpoints Reference

### 1. Health Probe
- `GET /health` or `GET /api/v1/health`

### 2. On-Demand PR Review
- `POST /api/v1/review/pr`
```json
{
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "pr_number": 42,
  "dry_run": true
}
```

### 3. GitHub Webhook Receiver
- `POST /api/v1/webhook/github`
- Validates `X-Hub-Signature-256` HMAC header.
- Automatically handles `pull_request` (`opened`, `synchronize`, `closed` with `merged`).

### 4. Developer Feedback
- `POST /api/v1/feedback`
```json
{
  "repo_full_name": "octocat/Hello-World",
  "feedback_type": "ACCEPTED",
  "finding_id": "finding-uuid",
  "comment": "Applied recommended fix."
}
```

### 5. Prometheus Metrics
- `GET /metrics`

---

## Testing & Quality Assurance

Run the complete test suite (42 tests):
```powershell
.\.venv\Scripts\pytest.exe -v
```

Run code style & linter check:
```powershell
.\.venv\Scripts\ruff.exe check app tests
```
