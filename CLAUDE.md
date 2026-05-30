# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Streamlit chatbot UI connected to a locally-served LLM (Ollama) via streaming REST, containerized with Docker, orchestrated with Kubernetes (local cluster via Docker Desktop), deployed via Helm, and automated through GitHub Actions CI/CD.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend UI | Streamlit |
| LLM Model | `lfm2.5-thinking:latest` (default in Helm); `gemma4:e2b` (default local) |
| LLM Serving | Ollama (runs on Windows host, NOT in the cluster) |
| Containerization | Docker |
| Container Orchestration | Kubernetes (Docker Desktop local cluster) |
| Kubernetes Package Management | Helm |
| CI/CD | GitHub Actions → Docker Hub |
| Image Registry | Docker Hub (`vamsidv2010/chatbot-simple`) |
| OS | Windows — use `helm.exe` not `helm` (name conflict with a Python script) |

## Architecture

`app.py` is the entire application — a single Streamlit file. It creates an `ollama.Client` at startup using `OLLAMA_HOST` and `MODEL_NAME` env vars, streams responses token-by-token with `st.write_stream`, and stores conversation history in `st.session_state.messages`.

Ollama always runs on the **Windows host**, never inside Kubernetes:
- Local dev: `http://localhost:11434` (default)
- In-cluster: `http://host.docker.internal:11434` (set in `helm/chatbot/values.yaml`)

CI (`.github/workflows/ci.yml`) triggers on every push to `main`, builds the image, and pushes two tags to Docker Hub: `:latest` and `:<git-sha>`. Requires `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` secrets.

## Common Commands

### Local development
```powershell
# Activate venv and run the app
.venv\Scripts\Activate.ps1
streamlit run app.py
# App is at http://localhost:8501
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

| Module | Description | Status |
|---|---|---|
| 1 | Chatbot UI (Streamlit) | ✅ Complete |
| 2 | GitHub + CI pipeline | ✅ Complete |
| 3 | Helm charts + Kubernetes deployment | ✅ Complete |
| 4 | ArgoCD automatic deployment | ✅ Built — pending deploy validation |

Track overall status in `PROGRESS.md`.

## Key Files

| File | Purpose |
|---|---|
| `app.py` | Entire Streamlit app |
| `helm/chatbot/values.yaml` | Image repo, Ollama host, model name, service type |
| `helm/chatbot/templates/deployment.yaml` | Pod spec; injects `OLLAMA_HOST` and `MODEL_NAME` as env vars |
| `.github/workflows/ci.yml` | Builds + pushes Docker image on push to `main` |
| `.agents/plans/` | Per-module implementation plans (canonical reference per task) |

## Planning Conventions

- Save all plans to `.agents/plans/` using naming `{sequence}.{plan-name}.md` (e.g., `3.helm-k8s.md`)
- Each plan must include at least one validation test per task
- Mark complexity at the top: ✅ Simple | ⚠️ Medium | 🔴 Complex
- 🔴 Complex plans must be broken into sub-plans before executing
- Custom commands: `.calude/commands/build.md` and `onboarding.md`

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
