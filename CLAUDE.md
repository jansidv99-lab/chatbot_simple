# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Streamlit chatbot UI connected to a locally-served LLM (Ollama) via streaming REST, containerized with Docker, orchestrated with Kubernetes (local cluster via Docker Desktop), deployed via Helm, and automated through GitHub Actions CI/CD.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend UI | Streamlit (multi-page: `app.py` + `pages/`) |
| LLM Model | `lfm2.5-thinking:latest` (default in Helm); `gemma4:e2b` (default local) |
| LLM Serving | Ollama (runs on Windows host, NOT in the cluster) |
| Containerization | Docker |
| Container Orchestration | Kubernetes (Docker Desktop local cluster) |
| Kubernetes Package Management | Helm |
| CI/CD | GitHub Actions → Docker Hub |
| Image Registry | Docker Hub (`vamsidv2010/chatbot-simple`) |
| Observability | Arize Phoenix (in-cluster) — OpenTelemetry + OpenInference conventions |
| Database | PostgreSQL |
| OS | Windows — use `helm.exe` not `helm` (name conflict) |

## Architecture

### Streamlit Multi-Page App

Streamlit auto-discovers pages from the `pages/` directory:
- `app.py` — main chat page; creates an `ollama.Client` at startup, streams responses token-by-token via `st.write_stream`, stores history in `st.session_state.messages`, calls `generate_suggestions` after each reply to populate 3 follow-up questions in the sidebar
- `pages/upload.py` — Excel ingestion page; validates → parses → inserts into PostgreSQL; calls `_init_schema()` once via `@st.cache_resource` on load

Ollama always runs on the **Windows host**, never inside Kubernetes:
- Local dev: `http://localhost:11434` (default)
- In-cluster: `http://host.docker.internal:11434` (set in `helm/chatbot/values.yaml`)

### Ingestion Pipeline

`pages/upload.py` → `ingestion/parser.py` → `ingestion/db.py`

The parser expects a Zerodha F&O positions `.xlsx` with a sheet named `F&O`, header row at row 15 (`Symbol` in B15), and data starting at row 16, columns B–L. `validate_file()` checks the sheet name, header cell, and presence of data rows before `parse_positions_excel()` maps columns to a dict. The DB layer uses `psycopg2` with `execute_values` and `ON CONFLICT (trade_date, symbol) DO NOTHING` — duplicate rows are silently skipped.

### Observability / Tracing

When `PHOENIX_ENDPOINT` is set, the app instruments itself via `OllamaInstrumentor` and wraps each chat turn in two nested OpenTelemetry spans using OpenInference `span.kind` attributes:

- `chat_turn` (kind=`AGENT`) — outer span covering the full user turn
  - `stream_response` (kind=`CHAIN`) — spans the streaming LLM call
  - `generate_suggestions` (kind=`CHAIN`) — spans the follow-up question generation

In-cluster, Phoenix receives traces at `http://phoenix:6006/v1/traces`. Phoenix is toggled via `values.yaml: phoenix.enabled`.

### CI Auto-Commit Behavior

After a successful Docker push, CI (`ci.yml`) automatically commits back to `main` updating `helm/chatbot/values.yaml` with the new image SHA tag. Commits from `github-actions[bot]` with `[skip ci]` in the message are this auto-update — not human changes.

## Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `MODEL_NAME` | `gemma4:e2b` | Model to use for chat and suggestions |
| `PHOENIX_ENDPOINT` | _(empty — disables tracing)_ | OTLP endpoint for Phoenix, e.g. `http://phoenix:6006/v1/traces` |
| `PHOENIX_PROJECT` | `chatbot` | Phoenix project name for trace grouping |
| `PG_HOST` | `localhost` | PostgreSQL host (`postgres` in-cluster) |
| `PG_PORT` | `5432` | PostgreSQL port |
| `PG_DB` | `chatbot` | PostgreSQL database name |
| `PG_USER` | `chatbot` | PostgreSQL user |
| `PG_PASSWORD` | `chatbot123` | PostgreSQL password (dev-only) |

## Common Commands

### Local development
```powershell
.venv\Scripts\Activate.ps1
streamlit run app.py
# App is at http://localhost:8501
```

### Lint and test
```powershell
.venv\Scripts\Activate.ps1
ruff check app.py pages/ ingestion/   # lint (matches CI)
pytest tests/ -v                       # all tests
pytest tests/test_chat.py::test_yields_tokens -v      # single chat test
pytest tests/test_ingestion.py -v                     # ingestion tests (requires real fixture file)
```

> **Note:** `tests/test_ingestion.py` depends on `raw_data_files/daily_poistions/positions-19-5.xlsx` being present (the directory name "poistions" is a typo — don't rename it; the test path is hardcoded).

### Local PostgreSQL (for upload page)
```powershell
docker run -d --name pg -e POSTGRES_DB=chatbot -e POSTGRES_USER=chatbot -e POSTGRES_PASSWORD=chatbot123 -p 5432:5432 postgres:16-alpine
```

### Docker
```powershell
docker build -t chatbot-simple .
docker run -p 8501:8501 -e OLLAMA_HOST=http://host.docker.internal:11434 chatbot-simple
```

### Helm / Kubernetes (use helm.exe, not helm)
```powershell
helm.exe lint helm/chatbot                              # Lint
helm.exe install chatbot helm/chatbot --dry-run --debug # Preview manifests
helm.exe install chatbot helm/chatbot                   # Deploy
helm.exe upgrade chatbot helm/chatbot                   # Upgrade after changes
helm.exe uninstall chatbot                              # Remove

kubectl get pods                         # Verify pod is Running
kubectl get svc                          # EXTERNAL-IP should be localhost
kubectl logs deployment/chatbot-chatbot  # Check for errors
# App is at http://localhost:8501
```

### Ollama (must be running before the app starts)
```powershell
ollama serve
ollama pull gemma4:e2b       # for local dev
ollama pull lfm2.5-thinking  # for k8s (matches values.yaml)
```

### Phoenix Observability
```powershell
# Port-forward UI (run in a dedicated terminal)
kubectl port-forward svc/phoenix 6006:6006
# UI at http://localhost:6006 — shows all LLM traces

# Check Phoenix pod
kubectl get pods -l app=phoenix
kubectl logs deployment/chatbot-phoenix

# Disable Phoenix (edit values.yaml: phoenix.enabled: false, then upgrade)
helm.exe upgrade chatbot helm/chatbot
```

### ArgoCD (one-time install)
```powershell
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=300s
kubectl apply -f argocd/application.yaml   # deploy the GitOps Application
```

### ArgoCD (day-to-day)
```powershell
# Port-forward UI — run in a dedicated terminal, keep it running
kubectl port-forward svc/argocd-server -n argocd 8080:443
# UI at https://localhost:8080 (accept self-signed cert)

# Get initial admin password
$b64 = kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}"
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64))

# CLI (download argocd-windows-amd64.exe, put on PATH)
argocd.exe login localhost:8080 --username admin --insecure
argocd.exe app get chatbot      # sync + health status
argocd.exe app list             # all apps at a glance
argocd.exe app sync chatbot     # force sync without waiting for poll
argocd.exe app diff chatbot     # diff: Git vs cluster
```

## Development Phases

Track overall status in `PROGRESS.md`.

## Planning Conventions

- Save all plans to `.agents/plans/` using naming `{sequence}.{plan-name}.md` (e.g., `3.helm-k8s.md`)
- Each plan must include at least one validation test per task
- Mark complexity at the top: ✅ Simple | ⚠️ Medium | 🔴 Complex
- 🔴 Complex plans must be broken into sub-plans before executing
- Custom commands live in `.calude/commands/` (note: directory name is a typo — kept as-is): `/build` executes a plan file, `/onboarding` scans the repo and summarises project state

## Behavioral Guidelines

### Think Before Coding

- State assumptions explicitly; ask if uncertain
- Surface multiple interpretations rather than picking silently
- Name what's confusing and stop; don't guess

### Simplicity First

- Minimum code that solves the problem — nothing speculative
- No abstractions, flexibility, or configurability beyond what was asked
- If you write 200 lines and it could be 50, rewrite it

### Surgical Changes

- Touch only what the request requires; don't improve adjacent code
- Match existing style even if you'd do it differently
- Remove imports/variables made unused by YOUR changes only; leave pre-existing dead code alone

### Goal-Driven Execution

For multi-step tasks, state a brief plan before coding:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
```
Transform vague tasks into verifiable goals before starting.

## Claude Code Skills — When to Use

| Skill | When |
|---|---|
| `engineering:deploy-checklist` | Before every `helm.exe upgrade` |
| `engineering:debug` | LLM unreachable from pod; unexpected errors |
| `engineering:architecture` | ADR decisions (e.g. ArgoCD sync strategy changes) |
| `security-review` | Before pushing CI changes; before ArgoCD RBAC setup |
| `verify` | After any deploy — confirm app loads and chat works |
| `loop` | Polling a long-running deploy or CI run |
| `engineering:standup` | Daily — summarize commits and today's plan |
