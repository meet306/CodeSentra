# CodeSentra: AI-Powered GitHub PR Reviewer

[![Python 3.11](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com/)
[![Groq](https://img.shields.io/badge/Groq%20API-Free%20Tier-orange.svg)](https://groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

An intelligent, event-driven GitHub Pull Request Code Review System built entirely using free and open-source technologies, optimized for lightweight local execution on 8 GB RAM machines.

---

## Key Features (Phase 1)

- **Real GitHub REST Integration**: Fetches real PR metadata, changed files, patch diffs, and unified git diffs.
- **Groq Free Tier AI Engine**: High-speed inference using free-tier models (default: `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`).
- **Strict Pydantic Schema Validation**: Structured outputs for findings with severity (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `INFO`), confidence ratings, and reasoning.
- **Hallucination Protection**: Findings referencing non-existent files or invalid line numbers are discarded or normalized.
- **Rate Limit Resilience**: Automatic exponential backoff when hitting Groq or GitHub rate limits.
- **Diff & Memory Protection**: Automatic diff truncation (`MAX_DIFF_LINES`) and token budget protection to prevent overflowing free-tier context windows.
- **Prompt Injection Defense**: Untrusted PR code and comments are isolated inside defensive XML-style delimiters (`<untrusted_diff>`, `<pr_context>`).
- **Dry-Run Safety**: `DRY_RUN=true` by default prevents unintended comments from being posted to GitHub during development.

---

## Project Structure

```
CodeSentra/
├── app/
│   ├── main.py                     # FastAPI application factory & lifespan
│   ├── config.py                   # Pydantic Settings & configuration
│   ├── api/
│   │   ├── dependencies.py         # Dependency injection providers
│   │   └── routes/
│   │       ├── health.py           # Health check endpoints
│   │       └── review.py           # On-demand PR review endpoints
│   ├── core/
│   │   ├── errors.py               # Custom exceptions & handlers
│   │   └── logging.py              # Secret-redacting logger
│   ├── integrations/
│   │   ├── github.py               # GitHub REST API client
│   │   └── groq.py                 # Groq client with backoff & schema parsing
│   ├── schemas/
│   │   ├── github.py               # PR models & diff data structures
│   │   └── review.py               # Finding, Severity, and Review schemas
│   └── services/
│       └── reviewer/
│           └── review_service.py   # PR review orchestration service
├── tests/                          # Pytest test suite (17 tests)
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_github_integration.py
│   ├── test_groq_integration.py
│   ├── test_review_service.py
│   └── test_api_review.py
├── .env.example                    # Environment variable template
├── .gitignore
├── DEVELOPMENT_PROGRESS.md         # Phase tracking & test records
├── requirements.txt
└── pyproject.toml
```

---

## Quickstart Guide

### 1. Prerequisites
- Python 3.11+
- Windows OS (or Linux / macOS)
- Free Groq API Key: [https://console.groq.com/keys](https://console.groq.com/keys)
- (Optional) GitHub Personal Access Token (for higher rate limits on public/private repositories)

### 2. Environment Setup

Create `.env` from `.env.example`:
```powershell
Copy-Item .env.example .env
```

Edit `.env` with your free Groq API key:
```env
GROQ_API_KEY=gsk_your_actual_key_here
GROQ_MODEL=llama-3.3-70b-versatile
GITHUB_TOKEN=optional_github_token_here
DRY_RUN=true
```

### 3. Installation

Activate the virtual environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:
```powershell
pip install -r requirements.txt
```

### 4. Running the Application

Start the FastAPI development server:
```powershell
.\.venv\Scripts\uvicorn.exe app.main:app --host 127.0.0.1 --port 8000 --reload
```

The server is available at:
- **Interactive OpenAPI Documentation**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)

---

## API Endpoints

### 1. Health Check
`GET /health` or `GET /api/v1/health`

**Sample Response:**
```json
{
  "status": "healthy",
  "app_name": "CodeSentra AI PR Reviewer",
  "environment": "development",
  "version": "0.1.0",
  "dry_run": true,
  "integrations": {
    "groq_configured": true,
    "groq_model": "llama-3.3-70b-versatile",
    "github_token_configured": false
  }
}
```

### 2. Trigger Code Review
`POST /api/v1/review/pr`

**Request Body:**
```json
{
  "repo_owner": "octocat",
  "repo_name": "Hello-World",
  "pr_number": 42,
  "dry_run": true
}
```

**Response Body:**
```json
{
  "repo": "octocat/Hello-World",
  "pr_number": 42,
  "title": "Add authentication module",
  "author": "octocat",
  "status": "completed",
  "dry_run": true,
  "summary": {
    "total_findings": 1,
    "critical_count": 0,
    "high_count": 1,
    "medium_count": 0,
    "low_count": 0,
    "info_count": 0,
    "overview": "The PR introduces password authentication. A critical cryptographic weakness was observed in password hashing."
  },
  "findings": [
    {
      "agent_name": "phase1_ai_reviewer",
      "title": "Insecure MD5 password hashing",
      "description": "MD5 algorithm is used to hash passwords without salt or work factor.",
      "severity": "HIGH",
      "confidence": 0.95,
      "file_path": "src/auth.py",
      "line_number": 5,
      "code_snippet": "return hashlib.md5(password.encode()).hexdigest()",
      "suggested_fix": "Use argon2-cffi or bcrypt for password hashing.",
      "reasoning": "MD5 lacks collision resistance and allows trivial rainbow-table attacks."
    }
  ],
  "execution_time_seconds": 1.45,
  "model_used": "llama-3.3-70b-versatile",
  "tokens_consumed": {
    "prompt_tokens": 420,
    "completion_tokens": 150,
    "total_tokens": 570
  }
}
```

---

## Testing

Run tests with pytest:
```powershell
.\.venv\Scripts\pytest.exe -v
```

Run linting with Ruff:
```powershell
.\.venv\Scripts\ruff.exe check app
```
