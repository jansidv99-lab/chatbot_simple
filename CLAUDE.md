# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Streamlit chatbot UI connected to a locally-served LLM (Gemma4:e2b via Ollama), containerized with Docker, orchestrated with Kubernetes (local cluster), deployed via Helm, and automated through GitHub Actions CI/CD.

## Tech Stack

| Layer | Choice |
|---|---|
| Frontend UI | Streamlit |
| LLM Model | Gemma4:e2b (7.2 GB) |
| LLM Serving | Ollama (local, not in Kubernetes) |
| Containerization | Docker |
| Container Orchestration | Kubernetes (local cluster) |
| Kubernetes Package Management | Helm |
| CI/CD | GitHub Actions |
| Image Registry | Docker Hub |
| OS | Windows |

## Development Phases

- **Module 1** — Chatbot UI (Streamlit)
- **Module 2** — GitHub repo + CI pipeline (GitHub Actions)
- **Module 3** — Helm charts and Kubernetes deployment
- **Module 4** — LLM (Ollama) integration with Kubernetes
- **Module 5** — ArgoCD for automatic deployment

## Planning Conventions

- Save all plans to `.agent/plans/` using naming `{sequence}.{plan-name}.md` (e.g., `1.chatbot-ui.md`)
- Each plan must include at least one validation test per task
- Mark complexity at the top: ✅ Simple | ⚠️ Medium | 🔴 Complex
- 🔴 Complex plans must be broken into sub-plans before executing

## Development Flow

1. **Plan** — Create a detailed plan in `.agent/plans/`
2. **Build** — Execute the plan
3. **Validate** — Test and verify; use browser testing where applicable
4. **Iterate** — Fix issues found during validation

Track overall status in `PROGRESS.md`.

## Claude Code Skills — When to Use

### Module 1 — Chatbot UI (Streamlit)

| Skill | When to use |
|---|---|
| `/init` | Once at the start — generates CLAUDE.md from the codebase |
| `engineering:system-design` | Before writing any code — design the Streamlit app structure, Ollama API integration shape |
| `engineering:architecture` | When deciding how the UI talks to Ollama (REST vs SDK, streaming vs blocking) |
| `engineering:testing-strategy` | Before building — decide what to test in a Streamlit app |
| `run` | After building — launch the app and verify the chat UI works end-to-end |
| `verify` | After any change — confirm it still works in the browser |
| `code-review` | Before moving to Module 2 — catch issues early |

### Module 2 — GitHub + CI Pipeline

| Skill | When to use |
|---|---|
| `engineering:documentation` | Write the README, runbook for CI setup |
| `security-review` | Before pushing — check Actions workflows for secret leaks, injection risks |
| `code-review` | Review the GitHub Actions YAML before merging |
| `update-config` | Configure Claude Code hooks (e.g., auto-lint before commits) |

### Module 3 — Helm Charts & Kubernetes Deployment

| Skill | When to use |
|---|---|
| `engineering:system-design` | Design the Kubernetes service topology (Streamlit pod ↔ Ollama service) |
| `engineering:architecture` | ADR for Helm vs raw manifests, ConfigMap vs Secrets strategy |
| `engineering:deploy-checklist` | Before every `helm upgrade` — verify readiness, rollback plan |
| `verify` | After deploy — confirm the app is reachable in the cluster |
| `security-review` | Check Helm values for exposed secrets or overly permissive RBAC |

### Module 4 — Ollama Integration with Kubernetes

| Skill | When to use |
|---|---|
| `engineering:system-design` | Design how Ollama runs (sidecar vs separate pod, PVC for model weights) |
| `engineering:debug` | When the LLM isn't reachable from the Streamlit pod |
| `engineering:testing-strategy` | Define integration tests for the Ollama ↔ Streamlit path |
| `verify` | Confirm model inference works inside the cluster |
| `claude-api` | Only if you swap Ollama for the Anthropic API |

### Module 5 — ArgoCD (GitOps)

| Skill | When to use |
|---|---|
| `engineering:architecture` | ADR for ArgoCD sync strategy (auto vs manual, App-of-Apps pattern) |
| `engineering:deploy-checklist` | Before enabling auto-sync on production |
| `engineering:incident-response` | When ArgoCD drifts or a bad sync breaks the cluster |
| `security-review` | Review ArgoCD RBAC and repo access permissions |
| `schedule` | Set up scheduled Claude routines to check deploy status periodically |

### Ongoing — Any Module

| Skill | When to use |
|---|---|
| `engineering:standup` | Daily — summarize yesterday's commits and today's plan |
| `engineering:tech-debt` | End of each module — identify shortcuts taken |
| `simplify` | After any implementation — trim over-engineered code |
| `engineering:debug` | Whenever something breaks unexpectedly |
| `fewer-permission-prompts` | After a few sessions — reduce repetitive approval prompts |
| `loop` | Polling a long-running deploy or CI run |

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
