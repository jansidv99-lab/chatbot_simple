# Chatbot Simple

A Streamlit chat UI backed by a locally-running LLM (Ollama), fully containerized, deployed to Kubernetes via Helm, with GitOps automation through ArgoCD and a CI pipeline on GitHub Actions.

---

## Quick Start (local, < 5 minutes)

**Prerequisites:** Python 3.11+, [Ollama](https://ollama.com) installed and running.

```powershell
# 1. Pull a model
ollama pull gemma4:e2b

# 2. Clone and set up
git clone https://github.com/jansidv99-lab/chatbot_simple.git
cd chatbot_simple
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# 3. Run
streamlit run app.py
```

Open `http://localhost:8501`. Start chatting.

---

## Features

- **Streaming responses** — tokens appear as they're generated
- **Conversation history** — full multi-turn context sent to the model each time
- **Follow-up suggestions** — 2–3 questions automatically suggested after each reply
- **Clear conversation** — sidebar button resets the session
- **Graceful errors** — clear messages if Ollama isn't running or the model isn't pulled

---

## Configuration

All config is via environment variables. Copy `.env.example` or set them directly:

| Variable | Default | Description |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | URL of the Ollama server |
| `MODEL_NAME` | `gemma4:e2b` | Model to use for chat and suggestions |

Create a `.env` file at the project root to override locally:

```env
OLLAMA_HOST=http://localhost:11434
MODEL_NAME=gemma4:e2b
```

---

## Stack

| Layer | Choice |
|---|---|
| UI | Streamlit |
| LLM serving | Ollama (runs on host, not in cluster) |
| Container | Docker (`python:3.11-slim`) |
| Orchestration | Kubernetes — Docker Desktop local cluster |
| Helm chart | `helm/chatbot/` |
| GitOps | ArgoCD (`argocd/application.yaml`) |
| CI/CD | GitHub Actions → Docker Hub |
| Image registry | Docker Hub (`vamsidv2010/chatbot-simple`) |

---

## Running with Docker

```powershell
docker build -t chatbot-simple .
docker run -p 8501:8501 -e OLLAMA_HOST=http://host.docker.internal:11434 chatbot-simple
```

---

## Kubernetes Deployment (Helm)

> Requires Docker Desktop with Kubernetes enabled and `helm.exe` on PATH.

```powershell
# First deploy
helm.exe install chatbot helm/chatbot

# Upgrade after changes
helm.exe upgrade chatbot helm/chatbot

# Remove
helm.exe uninstall chatbot
```

App is at `http://localhost:8501`. Ollama must be running on the Windows host (`ollama serve`).

**Key values in `helm/chatbot/values.yaml`:**

```yaml
image:
  repository: vamsidv2010/chatbot-simple
  tag: latest              # overwritten by CI with the git SHA

ollama:
  host: http://host.docker.internal:11434
  model: lfm2.5-thinking:latest
```

---

## GitOps with ArgoCD

ArgoCD watches the `helm/chatbot/` path on `main` and auto-syncs on every change.

### One-time install

```powershell
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
kubectl wait --for=condition=Ready pods --all -n argocd --timeout=300s

# Uninstall existing Helm release first (ArgoCD takes ownership)
helm.exe uninstall chatbot

# Deploy the ArgoCD Application
kubectl apply -f argocd/application.yaml
```

### Access the UI

```powershell
# Run in a dedicated terminal — keep it open
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

UI at `https://localhost:8080`. Get the initial admin password:

```powershell
$b64 = kubectl get secret argocd-initial-admin-secret -n argocd -o jsonpath="{.data.password}"
[System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($b64))
```

### Day-to-day

```powershell
argocd.exe login localhost:8080 --username admin --insecure
argocd.exe app get chatbot       # sync + health status
argocd.exe app sync chatbot      # force sync without waiting for poll
argocd.exe app diff chatbot      # diff: Git vs cluster
```

### GitOps deploy flow

```
git push → GitHub Actions builds image → stamps image.tag SHA in values.yaml
         → commits [skip ci] → ArgoCD polls Git (every ~3 min)
         → detects values.yaml change → helm upgrade → new pod starts
```

---

## CI Pipeline

Defined in `.github/workflows/ci.yml`. Two jobs:

| Job | Trigger | Steps |
|---|---|---|
| `validate` | push + pull_request to `main` | install deps → `ruff` lint → `helm lint` → `pytest` |
| `build-and-push` | push to `main` only (after validate) | docker build + push → update `image.tag` in `values.yaml` → commit `[skip ci]` |

**Required GitHub secrets:**

| Secret | Purpose |
|---|---|
| `DOCKERHUB_USERNAME` | Docker Hub login |
| `DOCKERHUB_TOKEN` | Docker Hub access token (not password) |

---

## Tests

```powershell
.venv\Scripts\Activate.ps1
pytest tests/ -v
```

Tests cover `stream_response()` and `generate_suggestions()` — no running Ollama needed (uses mocks).

---

## Project Structure

```
app.py                        # entire Streamlit application
requirements.txt              # runtime + dev dependencies
Dockerfile                    # python:3.11-slim image
helm/chatbot/                 # Helm chart
  values.yaml                 # image, service, Ollama config
  templates/
    deployment.yaml
    service.yaml
argocd/
  application.yaml            # ArgoCD Application CR
.github/workflows/ci.yml      # GitHub Actions CI
tests/
  test_chat.py                # pytest tests
.agents/plans/                # per-module implementation plans
```

---

## Module History

| Module | What was built |
|---|---|
| 1 | Streamlit chat UI with streaming and history |
| 2 | Dockerfile + GitHub Actions CI (build + push to Docker Hub) |
| 3 | Helm chart, Kubernetes deployment, LoadBalancer service |
| 4 | ArgoCD GitOps — auto-deploy on every push to `main` |
| 5 | CI validate job: lint + helm lint + pytest gating builds |
| 6 | Auto follow-up question suggestions after each response |
