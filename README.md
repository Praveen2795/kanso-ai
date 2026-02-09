# Kanso.AI — AI-Powered Project Planning with Multi-Agent System

<div align="center">

**Turn any goal into a detailed, dependency-aware Gantt chart using a collaborative AI agent pipeline**

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-3776AB.svg?logo=python&logoColor=white)](https://python.org)
[![React 19](https://img.shields.io/badge/React-19-61DAFB.svg?logo=react&logoColor=black)](https://react.dev)
[![Google ADK](https://img.shields.io/badge/Google_ADK-Agent_Framework-4285F4.svg?logo=google&logoColor=white)](https://google.github.io/adk-docs/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

</div>

---

## Table of Contents

- [What is Kanso.AI?](#-what-is-kansoai)
- [Key Features](#-key-features)
- [How It Works — The Agent Pipeline](#-how-it-works--the-agent-pipeline)
- [Architecture Overview](#-architecture-overview)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Configuration Reference](#-configuration-reference)
- [API Reference](#-api-reference)
- [Data Models](#-data-models)
- [Observability & Evaluation with Opik](#-observability--evaluation-with-opik)
  - [1. Full-Pipeline Tracing](#1-full-pipeline-tracing-via-opiktracer)
  - [2. Rich Trace Metadata](#2-rich-trace-metadata)
  - [3. Datasets & Experiments](#3-datasets--experiments)
  - [4. Custom & Built-in Metrics (9 Total)](#4-custom--built-in-evaluation-metrics-9-total)
  - [5. Online Evaluation Rules](#5-online-evaluation-rules)
  - [6. Agent Optimizer](#6-opik-agent-optimizer)
  - [7. Experiment Results](#7-experiment-results)
- [Technology Stack](#-technology-stack)
- [Development Guide](#-development-guide)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 What is Kanso.AI?

Kanso.AI is a full-stack application that transforms any goal — a startup launch, a wedding, a home renovation, a software project — into a **detailed, dependency-aware project plan** visualized as an interactive Gantt chart.

It uses a **multi-agent AI system** built on [Google's Agent Development Kit (ADK)](https://google.github.io/adk-docs/) where specialized agents collaborate through a structured pipeline:

1. **Analyze** — Understand the user's goal, ask clarifying questions if ambiguous
2. **Research** — Use Google Search grounding to gather real-world context
3. **Architect** — Design the project structure (Phases → Tasks → Subtasks → Dependencies)
4. **Estimate** — Calculate realistic durations using bottom-up estimation with complexity-based buffers
5. **Validate** — Review the plan through automated quality control loops (max 2 iterations)
6. **Refine** — Allow the user to chat with a Project Manager agent to adjust the plan

The name "Kanso" (簡素) comes from the Japanese aesthetic principle meaning **simplicity and elimination of clutter** — turning complex project planning into a simple, beautiful experience.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **Multi-Agent Pipeline** | 7 specialized AI agents (Analyst, Researcher, Architect, Estimator, 3 Reviewers) collaborate to create plans |
| 🔄 **Validation Loops** | Structure and estimate reviewers can reject and request revisions (up to 2 iterations) |
| 📊 **Interactive Gantt Chart** | Visualize timeline with duration bars, buffer segments (diagonal stripes), and phase grouping |
| 💬 **Chat Refinement** | Conversational Project Manager agent modifies the plan — "make it shorter", "add a testing phase", "remove buffers" |
| 📎 **File Upload** | Attach reference documents (PDF, images, text) for additional context during analysis |
| ⚡ **Real-time Agent Status** | WebSocket connection shows which agent is active, with iteration badges during validation loops |
| 📅 **Calendar Export** | Export your plan to Google Calendar or Outlook (.ics format) |
| 🔍 **Google Search Grounding** | Agents use Google Search via ADK tools to research best practices and validate technical terms |
| 📈 **Opik Observability** | Full LLM tracing, LLM-as-judge evaluation, cost/token tracking via Comet Opik (optional) |

---

## 🤖 How It Works — The Agent Pipeline

### Overview

When a user submits a project idea, the backend orchestrates a **sequential agent pipeline** where each agent builds on the previous one's output. The pipeline includes two **validation loops** with a maximum of 2 retry iterations each.

```
USER INPUT: "Plan a 2-week Japan trip for 2 people, $5000 budget"
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  1. ANALYST AGENT  (Gemini 2.5 Pro)                      │
│     • Checks if the request is clear and complete        │
│     • Uses Google Search to validate terms/URLs          │
│     • Returns clarifying questions OR signals "ready"    │
│     Output: ClarificationOutput {needsClarification,     │
│             questions[], reasoning}                      │
└──────────────────────────────────────────────────────────┘
    │
    │  If questions → sent to user → user answers → re-analyze
    │  If ready → proceed
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  2. ARCHITECT AGENT  (Gemini 2.5 Pro)                    │
│     • Researches domain best practices via Google Search │
│     • Creates: Phases → Tasks → Subtasks → Dependencies │
│     • Each task gets: id, name, phase, complexity,       │
│       description, subtasks[], dependencies[]            │
│     Output: ProjectPlanOutput {projectTitle, tasks[]}    │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  3. STRUCTURE REVIEWER  (Gemini 2.5 Flash)               │
│     • Validates dependency logic (can't test before build)│
│     • Checks completeness (software project needs testing)│
│     • Verifies subtask specificity (no vague "do stuff") │
│     • Ensures dependency IDs reference real task IDs     │
│     Output: ValidationOutput {isValid, critique}         │
│                                                          │
│     ┌─── If INVALID ──► Architect retries with critique  │
│     │    (up to 2 iterations total)                      │
│     └─── If VALID ──► proceed                            │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  4. ESTIMATOR AGENT  (Gemini 2.5 Pro)                    │
│     • Bottom-up estimation: estimate each subtask first  │
│     • Aggregates subtask durations to parent task        │
│     • Adds complexity-based buffers:                     │
│       Low=10-15%, Medium=20-25%, High=25-30%             │
│     • Sets duration and buffer fields (in hours)         │
│     Output: ProjectPlanOutput (with durations & buffers) │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  5. ESTIMATE REVIEWER  (Gemini 2.5 Flash)                │
│     • Sanity-checks: "1 hour to build entire backend"=NO │
│     • Validates buffer inclusion (high complexity needs   │
│       25-30% buffer)                                     │
│     • Checks subtask aggregation matches parent duration │
│     Output: ValidationOutput {isValid, critique}         │
│                                                          │
│     ┌─── If INVALID ──► Estimator retries with critique  │
│     │    (up to 2 iterations total)                      │
│     └─── If VALID ──► proceed                            │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  6. FINAL REVIEWER  (Gemini 2.5 Flash)                   │
│     • Ensures all durations > 0                          │
│     • Verifies all dependency IDs exist                  │
│     • Cleans up formatting issues                        │
│     • Does NOT add or remove tasks                       │
│     Output: ProjectPlanOutput (cleaned)                  │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  7. SCHEDULER (deterministic algorithm, not an LLM)      │
│     • Topological sort with cycle detection              │
│     • Calculates startOffset for each task based on      │
│       dependency chain (predecessor end times)           │
│     • Resolves parallel vs sequential execution          │
│     • Computes total project duration                    │
│     Output: Task[] with calculated startOffset values    │
└──────────────────────────────────────────────────────────┘
    │
    ▼
  GANTT CHART rendered in browser
    │
    ▼ (user can now chat)
┌──────────────────────────────────────────────────────────┐
│  MANAGER AGENT  (Gemini 2.5 Pro) — Chat Phase            │
│     • "Make it shorter" → reduces durations              │
│     • "Add a marketing phase" → adds new tasks           │
│     • "What's the timeline?" → explains without changes  │
│     • Must return ALL tasks (not just modified ones)      │
│     • Strict scope: refuses off-topic questions           │
│     Output: ChatOutput {reply, updatedPlan?}             │
│                                                          │
│     When updatedPlan is returned:                        │
│       → Smart merge preserves existing task data         │
│       → Scheduler recalculates all startOffsets          │
│       → Gantt chart re-renders                           │
└──────────────────────────────────────────────────────────┘
```

### Validation Loop Detail

The validation loops prevent low-quality plans from reaching the user:

```
Architect creates plan
    │
    └──► Structure Reviewer validates
              │
              ├── PASS → move to Estimator
              │
              └── FAIL → critique sent back to Architect
                          Architect creates new plan WITH critique in prompt
                          │
                          └──► Structure Reviewer validates again
                                    │
                                    ├── PASS → move to Estimator
                                    └── FAIL → accept as-is (max 2 iterations reached)
```

The same pattern applies between the Estimator and Estimate Reviewer.

**Why max 2 iterations?** Empirically, more iterations lead to diminishing returns and increased latency. Two passes catch most structural and estimation issues.

### Smart Task Merging (Chat Phase)

When the Manager agent returns an `updatedPlan`, the orchestrator runs a **merge algorithm** because LLMs sometimes return incomplete data:

1. **Raw value detection** — Check the raw LLM response for each field BEFORE Pydantic validation (important because Pydantic coerces `null` → default values)
2. **Selective update** — Only update `duration`/`buffer` if the LLM explicitly provided non-null values; otherwise preserve the existing task's values
3. **New task detection** — Tasks with IDs not in the original plan are added
4. **Re-scheduling** — After merge, the scheduler recalculates all `startOffset` values

This prevents a common failure mode where the LLM returns `"duration": null` and the Gantt chart breaks.

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────┐         ┌──────────────────────────────────┐
│           FRONTEND                  │         │           BACKEND                │
│  React 19 + TypeScript + Vite       │         │  FastAPI + Python 3.11+          │
│  TailwindCSS for styling            │         │  Google ADK for agents           │
│                                     │         │                                  │
│  ┌─────────────────────────────┐    │   REST  │  ┌────────────────────────────┐  │
│  │ App.tsx                     │    │ ◄─────► │  │ main.py (FastAPI app)      │  │
│  │ • State: IDLE → CLARIFYING  │    │         │  │ • REST endpoints           │  │
│  │   → GENERATING → READY      │    │   WS    │  │ • WebSocket /ws/{clientId} │  │
│  │ • Chat panel                │    │ ◄═════► │  │ • ConnectionManager        │  │
│  │ • File upload               │    │         │  └────────┬───────────────────┘  │
│  └──────┬──────────────────────┘    │         │           │                      │
│         │                           │         │  ┌────────▼───────────────────┐  │
│  ┌──────▼──────────────────────┐    │         │  │ orchestrator.py            │  │
│  │ apiService.ts               │    │         │  │ • Runs agent pipeline      │  │
│  │ • WebSocketService class    │    │         │  │ • Validation loops         │  │
│  │ • REST client functions     │    │         │  │ • Smart task merging       │  │
│  │ • Auto-reconnection logic   │    │         │  │ • Status broadcasting      │  │
│  └─────────────────────────────┘    │         │  └────────┬───────────────────┘  │
│                                     │         │           │                      │
│  ┌─────────────────────────────┐    │         │  ┌────────▼───────────────────┐  │
│  │ Components:                 │    │         │  │ Agents (Google ADK):       │  │
│  │ • AgentStatusDisplay        │    │         │  │ • analyst.py    (Pro)      │  │
│  │ • GanttChart                │    │         │  │ • architect.py  (Pro)      │  │
│  │ • ProjectDetails            │    │         │  │ • estimator.py  (Pro)      │  │
│  │ • ImpactBackground          │    │         │  │ • reviewer.py   (Flash)    │  │
│  └─────────────────────────────┘    │         │  │ • manager.py    (Pro)      │  │
│                                     │         │  │ • research.py   (Flash)    │  │
└─────────────────────────────────────┘         │  │ • scheduler.py  (algo)     │  │
                                                │  └────────────────────────────┘  │
                                                │                                  │
                                                │  ┌────────────────────────────┐  │
                                                │  │ Support modules:           │  │
                                                │  │ • models.py (Pydantic)     │  │
                                                │  │ • output_schemas.py        │  │
                                                │  │ • config.py (env settings) │  │
                                                │  │ • opik_service.py (traces) │  │
                                                │  │ • logging_config.py        │  │
                                                │  │ • middleware.py (CORS,logs) │  │
                                                │  │ • calendar_export.py       │  │
                                                │  └────────────────────────────┘  │
                                                └──────────────────────────────────┘
```

### Communication Flow

1. **User types a project idea** in the frontend
2. **Frontend opens a WebSocket** connection to `/ws/{clientId}`
3. **Frontend sends** `{"action": "analyze", "topic": "..."}` over WebSocket
4. **Backend orchestrator** runs the agent pipeline, sending `AgentStatusUpdate` messages over WebSocket at each step
5. **Frontend renders** the active agent in `AgentStatusDisplay` (with iteration badges during validation loops)
6. **When complete**, backend sends the final `ProjectData` over WebSocket
7. **Frontend renders** the Gantt chart and enables the chat panel
8. **User chats** → messages go via WebSocket `{"action": "chat", ...}` → Manager agent responds → Gantt updates

---

## 🗂️ Project Structure

```
kanso-ai/
├── README.md                           # This file
│
├── frontend/                           # React + TypeScript + Vite
│   ├── index.html                      # HTML entry point
│   ├── index.tsx                       # React DOM root
│   ├── App.tsx                         # Main component (state machine: IDLE→CLARIFYING→GENERATING→READY)
│   ├── types.ts                        # TypeScript interfaces (Task, ProjectData, AgentStatus, etc.)
│   ├── vite.config.ts                  # Vite build config with env variable injection
│   ├── tsconfig.json                   # TypeScript compiler config
│   ├── package.json                    # Dependencies: react 19, vite 6, typescript 5.8
│   ├── components/
│   │   ├── AgentStatusDisplay.tsx      # Shows active agent with progress steps & iteration badges
│   │   ├── GanttChart.tsx              # Interactive Gantt chart (duration bars + buffer stripes)
│   │   ├── ProjectDetails.tsx          # Expandable task tree with subtasks and assumptions
│   │   └── ImpactBackground.tsx        # Animated gradient background
│   └── services/
│       └── apiService.ts              # REST client + WebSocketService class with auto-reconnect
│
├── backend/                            # FastAPI + Google ADK
│   ├── run.py                          # Entry point: starts uvicorn server
│   ├── pyproject.toml                  # Python project config & dependencies (uv/pip compatible)
│   ├── .env.example                    # Template for environment variables
│   ├── README.md                       # Backend-specific docs (Opik setup, API details)
│   ├── run_evaluation.py               # CLI: seed datasets & run Opik experiments
│   ├── optimize_prompts.py             # Opik Agent Optimizer (MetaPromptOptimizer)
│   ├── setup_online_rules.py           # Sets up 4 automated Opik online eval rules via REST API
│   └── app/
│       ├── __init__.py
│       ├── config.py                   # Pydantic Settings — loads .env, defines all config
│       ├── models.py                   # Pydantic models for API request/response (Task, ProjectData, etc.)
│       ├── main.py                     # FastAPI app: REST endpoints + WebSocket + ConnectionManager
│       ├── middleware.py               # CORS middleware, request logging, correlation IDs
│       ├── logging_config.py           # Structured logging: JSON (prod) / human-readable (dev), rotation
│       ├── calendar_export.py          # .ics calendar file generation for Google Calendar / Outlook
│       └── agents/
│           ├── __init__.py             # Exports all agent factories and constants
│           ├── orchestrator.py         # Pipeline coordinator: runs agents, validation loops, merging
│           ├── analyst.py              # Analyst agent factory — request analysis & clarification
│           ├── architect.py            # Architect agent factory — project structure design
│           ├── estimator.py            # Estimator agent factory — bottom-up time estimation
│           ├── reviewer.py             # 3 reviewer factories + MAX_VALIDATION_ITERATIONS=2
│           ├── manager.py              # Manager agent factory — chat-based plan refinement
│           ├── research.py             # Research agent — Google Search grounding & URL content extraction
│           ├── scheduler.py            # Deterministic scheduler — topological sort for startOffset
│           ├── output_schemas.py       # Pydantic output schemas for agent responses (with field_validators)
│           ├── tools.py                # Shared tools: get_current_date(), google_search
│           ├── opik_service.py         # Opik integration: tracing, LLM-as-judge eval, cost tracking
│           └── evaluation.py           # Evaluation framework: benchmark dataset, 9 metrics, experiment runners
│
├── OPIK_INTEGRATION.md                 # Deep-dive: Opik integration docs (datasets, metrics, optimizer, rules)
└── .gitignore                          # Ignores: .env, node_modules, __pycache__, .venv, venv, dist
```

### File-by-File Guide

#### Backend Core

| File | Lines | Purpose | Key Concepts |
|------|-------|---------|-------------|
| `config.py` | ~70 | Environment configuration | Pydantic `BaseSettings`, `@lru_cache` singleton, loads `.env` |
| `models.py` | ~166 | API data models | `Task`, `Subtask`, `ProjectData`, `ChatMessage`, `AgentStatusUpdate` — mirrors frontend `types.ts` |
| `main.py` | ~585 | FastAPI application | REST endpoints (`/api/analyze`, `/api/generate`, `/api/chat`), WebSocket handler, `ConnectionManager` for multi-client support |
| `middleware.py` | ~172 | HTTP middleware | CORS config, request logging with correlation IDs, timing |
| `logging_config.py` | ~333 | Logging system | JSON formatter (production), console formatter (dev), log rotation, `@log_execution_time` decorator |
| `calendar_export.py` | — | Calendar export | Converts `ProjectData` → `.ics` file with configurable hours/day and weekend settings |

#### Backend Agents

| File | Lines | Model Used | Purpose | Input → Output |
|------|-------|-----------|---------|---------------|
| `analyst.py` | ~80 | Gemini 2.5 Pro | Analyzes requests, asks clarifying questions | Topic string → `ClarificationOutput` |
| `architect.py` | ~73 | Gemini 2.5 Pro | Designs project structure with phases & dependencies | Topic + context → `ProjectPlanOutput` |
| `estimator.py` | ~71 | Gemini 2.5 Pro | Bottom-up time estimation with buffers | `ProjectPlanOutput` → `ProjectPlanOutput` (with durations) |
| `reviewer.py` | ~129 | Gemini 2.5 Flash | 3 reviewers: structure, estimate, final | Plan → `ValidationOutput` {isValid, critique} |
| `manager.py` | ~120 | Gemini 2.5 Pro | Chat-based plan refinement | Plan + user message → `ChatOutput` {reply, updatedPlan?} |
| `research.py` | ~486 | Gemini 2.5 Flash | Google Search grounding, URL content extraction | Query → search results / URL content |
| `orchestrator.py` | ~813 | (coordinator) | Runs the full pipeline, validation loops, task merging | Topic → `ProjectData` (via status callbacks) |
| `scheduler.py` | ~83 | (algorithm) | Topological sort for dependency-aware scheduling | `Task[]` → `Task[]` with `startOffset` |
| `output_schemas.py` | ~90 | — | Pydantic schemas for agent outputs | `field_validators` coerce `None` → defaults |
| `tools.py` | ~25 | — | Shared agent tools | `get_current_date()`, `google_search` |
| `opik_service.py` | ~790 | — | Observability integration | LLM tracing, LLM-as-judge evaluation, cost tracking |

#### Frontend

| File | Lines | Purpose | Key Concepts |
|------|-------|---------|-------------|
| `App.tsx` | ~598 | Main component | State machine (`IDLE`→`CLARIFYING`→`GENERATING`→`READY`), chat panel, file upload, error handling |
| `types.ts` | ~65 | Type definitions | `Task`, `ProjectData`, `AgentType` enum, `AppState`, `ViewMode` |
| `apiService.ts` | ~464 | API client | `WebSocketService` class (connect, reconnect, message handling), REST functions, `recalculateSchedule()` |
| `AgentStatusDisplay.tsx` | — | Agent progress UI | Compact numbered pipeline (1→2→3→4), single active agent card with glow, iteration badges |
| `GanttChart.tsx` | ~441 | Gantt chart | SVG-based bars with duration + buffer (diagonal stripe pattern), phase grouping, tooltips, calendar export |
| `ProjectDetails.tsx` | — | Task details | Expandable task tree, subtask list, assumptions display |
| `ImpactBackground.tsx` | — | Visual effect | Animated gradient background canvas |

---

## 🚀 Getting Started

### Prerequisites

| Requirement | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.11+ | Backend runtime |
| **Node.js** | 18+ | Frontend build/dev |
| **uv** (recommended) or **pip** | latest | Python package manager |
| **Google AI API Key** | — | Required — powers all Gemini agents |

Get a Google AI API key from [Google AI Studio](https://aistudio.google.com/apikey) (free tier available).

### 1. Clone the Repository

```bash
git clone https://github.com/Praveen2795/kanso-ai.git
cd kanso-ai
```

### 2. Set Up the Backend

```bash
cd backend

# Option A: Using uv (recommended — faster, auto-creates venv)
uv sync

# Option B: Using pip
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
```

Configure environment:

```bash
cp .env.example .env
```

Edit `backend/.env` and add your Google AI API key:

```env
# Required
GOOGLE_API_KEY=your_google_api_key_here

# Optional: Opik observability (see Opik section below)
# OPIK_API_KEY=your_opik_api_key_here
# OPIK_WORKSPACE=your_workspace_name
```

Start the backend server:

```bash
# Using uv
uv run python run.py

# Using pip/venv
python run.py
```

The API will be available at `http://localhost:8000`. Visit `http://localhost:8000/docs` for interactive Swagger UI.

### 3. Set Up the Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at `http://localhost:5173`.

### 4. Use It

1. Open `http://localhost:5173` in your browser
2. Type a project idea (e.g., "Plan a 2-week Japan trip for 2 people")
3. Answer any clarifying questions the Analyst asks
4. Watch the agents build your plan in real-time
5. View the Gantt chart and chat with the Manager to refine it

---

## ⚙️ Configuration Reference

### Backend Environment Variables (`backend/.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_API_KEY` | **Yes** | — | Google AI API key for Gemini models |
| `HOST` | No | `0.0.0.0` | Server bind host |
| `PORT` | No | `8000` | Server port |
| `CORS_ORIGINS` | No | `http://localhost:5173,http://localhost:3000` | Comma-separated allowed CORS origins |
| `DEFAULT_MODEL` | No | `gemini-2.5-flash` | Model for reviewers & research (fast, cheaper) |
| `PRO_MODEL` | No | `gemini-2.5-pro` | Model for analyst, architect, estimator, manager (higher quality) |
| `ENVIRONMENT` | No | `development` | `development` / `staging` / `production` — affects log format |
| `LOG_LEVEL` | No | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` / `CRITICAL` |
| `ENABLE_FILE_LOGGING` | No | `false` | Write logs to `./logs/` with rotation |
| `LOG_MAX_BYTES` | No | `10485760` (10MB) | Max log file size before rotation |
| `LOG_BACKUP_COUNT` | No | `5` | Number of rotated log files to keep |
| `OPIK_API_KEY` | No | — | Comet Opik API key for observability |
| `OPIK_WORKSPACE` | No | — | Comet Opik workspace name |
| `OPIK_PROJECT_NAME` | No | `kanso-ai` | Opik project name |

### Frontend Environment Variables (`frontend/.env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://localhost:8000` | Backend REST API URL |
| `VITE_WS_URL` | `ws://localhost:8000` | Backend WebSocket URL |

---

## 📡 API Reference

### REST Endpoints

| Endpoint | Method | Description | Request Body | Response |
|----------|--------|-------------|-------------|----------|
| `/health` | GET | Health check | — | `{"status": "healthy"}` |
| `/api/analyze` | POST | Analyze a project request | `{topic, chatHistory[]}` | `{needsClarification, questions[], reasoning}` |
| `/api/generate` | POST | Generate complete plan | `{topic, context, file?}` | `ProjectData` |
| `/api/chat` | POST | Chat with project manager | `{project, message, history[]}` | `{reply, updatedPlan?}` |
| `/api/export-calendar` | POST | Export plan as .ics | `{project, startDate?, hoursPerDay?, includeWeekends?}` | `.ics` file |
| `/api/recalculate` | POST | Recalculate task scheduling | `{tasks[]}` | `{tasks[], totalDuration}` |
| `/api/opik/status` | GET | Opik observability status | — | `{enabled, workspace, traces_url}` |

### WebSocket Protocol

**Endpoint:** `ws://localhost:8000/ws/{clientId}`

**Client → Server Messages:**

```jsonc
// Analyze a project request
{"action": "analyze", "topic": "Build a mobile app", "chatHistory": []}

// Generate a full plan (after analysis)
{"action": "generate", "topic": "Build a mobile app", "context": "Additional context...", "file": null}

// Chat with manager (after plan is generated)
{"action": "chat", "project": { /* ProjectData */ }, "message": "Make it shorter", "history": []}

// Keep-alive ping
{"action": "ping"}
```

**Server → Client Messages:**

```jsonc
// Agent status update (during generation)
{"type": "agent_status", "data": {"active": true, "agent": "Architect", "message": "Designing project structure..."}}

// Analysis result
{"type": "analysis", "data": {"needsClarification": true, "questions": ["What is your budget?"], "reasoning": "..."}}

// Generated plan
{"type": "plan", "data": { /* ProjectData */ }}

// Chat response
{"type": "chat_response", "data": {"reply": "I've shortened the timeline.", "updatedPlan": { /* ProjectData */ }}}

// Error
{"type": "error", "data": {"message": "Something went wrong"}}

// Pong response
{"type": "pong"}
```

### Example: Generate a Plan via cURL

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Launch a Shopify store in 30 days",
    "context": "Budget is $5000, selling handmade jewelry, solo founder"
  }'
```

---

## 📦 Data Models

### Core Types (shared between frontend & backend)

```
Task
├── id: string              # Unique identifier (e.g., "phase1_task2")
├── name: string            # Display name
├── phase: string           # Phase grouping (e.g., "Phase 1: Research")
├── startOffset: number     # Hours from project start (calculated by scheduler)
├── duration: number        # Estimated hours of work
├── buffer: number          # Buffer hours (complexity-based, 10-30% of duration)
├── dependencies: string[]  # IDs of tasks that must complete first
├── description?: string    # Detailed description
├── complexity: "Low" | "Medium" | "High"
└── subtasks: Subtask[]
    ├── name: string
    ├── description?: string
    └── duration: number    # Hours

ProjectData
├── title: string
├── description: string
├── assumptions: string[]   # AI-generated planning assumptions
├── tasks: Task[]
└── totalDuration: number   # Total project hours (max task endTime)
```

### Agent Output Schemas (`output_schemas.py`)

These Pydantic models define the **structured output** that each agent must return. Google ADK enforces these schemas via the `output_schema` parameter on `LlmAgent`.

Key `field_validators` (prevent LLM null values from breaking the pipeline):
- `TaskOutput.duration`: `None` → `1.0` (default 1 hour)
- `TaskOutput.buffer`: `None` → `0.0`
- `SubtaskOutput.duration`: `None` → `0.5` (default 30 min)

---

## 🔭 Observability & Evaluation with Opik

Kanso.AI deeply integrates **[Opik](https://github.com/comet-ml/opik)** by Comet across the entire pipeline — from real-time trace collection during agent execution, through offline evaluation experiments with curated datasets, to automated prompt optimization and continuous production monitoring.

> 📄 **Even more details**: [OPIK_INTEGRATION.md](OPIK_INTEGRATION.md) — full architecture diagrams, metric scoring logic, hackathon alignment matrix, and all CLI commands.

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                          Opik Integration in Kanso.AI                            │
│                                                                                  │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│   │  1. Tracing   │    │ 2. Datasets  │    │  3. Online   │    │ 4. Agent     │  │
│   │   OpikTracer  │    │  & Experiments│    │   Eval Rules │    │  Optimizer   │  │
│   │   (per agent) │    │  (9 metrics)  │    │  (4 rules)   │    │ (MetaPrompt) │  │
│   └──────┬───────┘    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘  │
│          │                   │                   │                   │           │
│          └───────────────────┴───────────────────┴───────────────────┘           │
│                                      │                                           │
│                              ┌───────▼───────┐                                  │
│                              │  Comet / Opik  │                                  │
│                              │   Dashboard    │                                  │
│                              └───────────────┘                                  │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

### 1. Full-Pipeline Tracing via `OpikTracer`

Every request flows through the 7-agent pipeline with **complete trace visibility**. We use the official `OpikTracer` from Opik's ADK integration — every LLM call, tool invocation, agent handoff, and validation loop iteration is captured automatically:

```python
# backend/app/opik_service.py
from opik.integrations.adk import OpikTracer, track_adk_agent_recursive

tracer = OpikTracer(
    name="kanso-pipeline",
    tags=["kanso-ai", "project-planning", "multi-agent"],
    metadata={
        "pro_model": "gemini-2.5-pro",
        "judge_model": "gemini/gemini-2.5-flash",
        "framework": "google-adk",
    },
    project_name="kanso-ai",
)

# Recursively instrument ALL sub-agents so every LLM call is traced
instrumented_agent = track_adk_agent_recursive(agent, tracer)
```

**What gets captured per trace:**
- Full LLM input/output payloads for every agent (Analyst → Researcher → Architect → Reviewers → Estimator → Manager)
- Token usage (input + output tokens) per agent call
- Tool calls (Google Search grounding, URL extraction)
- Validation loop iterations and reviewer accept/reject decisions
- End-to-end pipeline timing with millisecond precision

The tracing is **non-intrusive** — if `OPIK_API_KEY` is not set, all Opik code silently degrades to no-ops via try/except guards:

```python
try:
    import opik
    from opik import track, opik_context
    from opik.integrations.adk import OpikTracer
    _opik_available = True
except ImportError:
    # Create dummy decorators — app works without Opik
    def track(*args, **kwargs): ...
```

---

### 2. Rich Trace Metadata

Beyond basic LLM input/output, we **enrich every trace** with structured metadata at three levels using `opik_context.update_current_span()` and `opik_context.update_current_trace()`:

#### Pipeline-Level Metadata (on the root trace)

Attached at the end of `generate_project_plan()` — gives a complete picture of the entire pipeline run:

```python
# backend/app/agents/orchestrator.py — generate_project_plan()
opik_context.update_current_trace(
    metadata={
        "pipeline_elapsed_seconds": total_elapsed,      # Total wall-clock time
        "stage_timings": {                               # Per-stage breakdown
            "architecture": 12.5,                        #   Architect + Structure Reviewer
            "estimation": 8.3,                           #   Estimator + Estimate Reviewer
            "finalize": 2.1,                             #   Final Reviewer + Scheduling
        },
        "architecture_iterations": 1,                    # How many architect retries
        "estimation_iterations": 2,                      # How many estimator retries
        "structure_validated": True,                      # Did structure pass review?
        "estimates_validated": True,                      # Did estimates pass review?
        "has_research_context": True,                     # Was Google Search used?
        "complexity_distribution": {                      # Task complexity breakdown
            "Low": 3, "Medium": 5, "High": 2
        },
        "task_count": 10,
        "total_duration_hours": 42.5,
        "phases": ["Design", "Development", "Testing"],
    }
)
```

#### Agent-Level Metadata (per agent span)

Each agent execution in `run_agent_with_status()` records its own span metadata:

```python
# backend/app/agents/orchestrator.py — run_agent_with_status()
opik_context.update_current_span(
    metadata={
        "agent_name": "architect",
        "agent_type": "pro_model",           # Which model tier (pro vs default)
        "execution_time_ms": 4523.7,         # Agent wall-clock time
        "response_length": 12840,            # Character count of agent output
        "model": "gemini-2.5-pro",
    }
)
```

#### Function-Level Metadata (specific orchestrator functions)

Individual functions like `analyze_request()` and `chat_with_manager()` record domain-specific metrics:

| Function | Tracked Fields |
|----------|---------------|
| `analyze_request()` | `topic_length`, `has_chat_history`, `needs_clarification`, `question_count`, `elapsed_seconds` |
| `chat_with_manager()` | `message_length`, `history_turns`, `project_task_count`, `has_plan_update`, `reply_length`, `elapsed_seconds` |
| `generate_project_plan()` | `pipeline`, `agents`, `pro_model`, `default_model`, `max_validation_iterations` |

---

### 3. Datasets & Experiments

We created a curated **benchmark dataset** (`kanso-planning-benchmark`) with **12 diverse project planning requests** stored in Opik, covering different complexity levels, domains, and edge cases:

| Category | Count | Examples | Purpose |
|----------|-------|----------|---------|
| **Simple/Clear** | 2 | Portfolio website, TODO API | Baseline — agent should NOT over-complicate |
| **Medium Complexity** | 3 | E-commerce platform, fitness app, CI/CD pipeline | Should handle multi-phase planning |
| **Complex/Enterprise** | 2 | Real-time whiteboard, fintech API gateway | Many dependencies, compliance, security |
| **Vague/Ambiguous** | 2 | "I want to build an app", "Make something with AI" | Tests analyst's clarification detection |
| **Hackathon-Themed** | 2 | Habit tracker, AI daily planner | Aligned with "Productivity & Work Habits" track |
| **Edge Case/Specific** | 1 | Distributed task queue with Redis Streams | Highly technical, tests domain understanding |

Each dataset item includes rich metadata for metric evaluation:

```python
{
    "input": "Build a real-time collaborative whiteboard with video chat",
    "context": "EdTech startup. WebSocket + WebRTC. Team of 4, 3 months.",
    "expected_traits": {
        "min_tasks": 10, "max_tasks": 25,
        "expected_phases": ["Architecture", "Core Canvas", "Video Integration", ...],
        "complexity": "complex",
        "domain": "fullstack"
    },
    "difficulty": "hard",
    "tags": ["fullstack", "real-time", "webrtc", "complex"]
}
```

**Two experiment types** run against this dataset:

| Experiment | Pipeline Tested | Agents Involved | Metrics Applied |
|------------|----------------|-----------------|-----------------|
| `plan` (full pipeline) | All 6 agents end-to-end | Researcher → Architect → Reviewers → Estimator → Manager | 9 metrics |
| `analyst` (analyst only) | Analyst agent only | Analyst | 4 metrics |

```bash
# Seed dataset (idempotent)
uv run python run_evaluation.py --seed

# Run named experiments
uv run python run_evaluation.py --experiment plan --name "plan-v3"
uv run python run_evaluation.py --experiment analyst --name "analyst-v2"
```

---

### 4. Custom & Built-in Evaluation Metrics (9 Total)

Experiments combine **5 custom domain-specific metrics** we wrote as `opik.BaseMetric` subclasses with **4 Opik built-in LLM-as-judge metrics** (powered by Gemini 2.5 Flash via LiteLLM):

#### Custom Metrics (deterministic heuristics — zero API calls, instant scoring)

| Metric Class | Name | What It Measures | Scoring Logic |
|-------------|------|------------------|---------------|
| `PlanHasRequiredFields` | `plan_structure_completeness` | All required plan fields present | Checks 9 structural fields: title, tasks, IDs, names, phases, durations, dependencies, subtasks, summary. Score = proportion present. |
| `TaskCountReasonableness` | `task_count_reasonableness` | Task count within expected range | Compares `len(tasks)` against `expected_traits.min_tasks`/`max_tasks`. Perfect if in range, scaled down proportionally outside. |
| `DurationRealism` | `duration_realism` | Realistic time estimates | Flags tasks < 0.5h or > 80h, buffer > duration. Score = 1 - (issues / total_tasks). |
| `PlanQualityLLMJudge` | `plan_quality_llm_judge` | Holistic plan quality | Uses Gemini to score requirement coverage, task granularity, logical flow, completeness (4 dimensions × 0.25 each). |
| `ClarificationQualityJudge` | `clarification_quality` | Analyst ambiguity detection | Uses Gemini to score correct detection, question quality, reasoning quality for the analyst agent. |

#### Opik Built-in LLM-as-Judge Metrics (via `gemini/gemini-2.5-flash`)

| Built-in Class | What It Measures | Configuration |
|---------------|------------------|---------------|
| `Hallucination` | Fabricated info not grounded in input | `model="gemini/gemini-2.5-flash"` |
| `AnswerRelevance` | Does the plan address the original request? | `model="gemini/gemini-2.5-flash"`, `require_context=False` |
| `Moderation` | Content safety check | `model="gemini/gemini-2.5-flash"` |
| `GEval` | Custom criteria evaluation | Task: "evaluating an AI-generated project plan", Criteria: logical tasks, realistic estimates, technology choices, request coverage, valid JSON |
| `IsJson` | Valid JSON output check | No model needed — deterministic |

```python
# backend/app/evaluation.py — run_plan_quality_experiment()
from opik.evaluation.metrics import Hallucination, AnswerRelevance, Moderation, GEval, IsJson

metrics = [
    # Custom heuristic metrics (instant, no API calls)
    TaskCountReasonableness(),
    PlanHasRequiredFields(),
    DurationRealism(),
    # Custom LLM-as-judge
    PlanQualityLLMJudge(),
    # Opik built-in LLM-as-judge (via LiteLLM → Gemini)
    Hallucination(model=JUDGE_MODEL),
    AnswerRelevance(model=JUDGE_MODEL, require_context=False),
    Moderation(model=JUDGE_MODEL),
    IsJson(),
    GEval(
        model=JUDGE_MODEL,
        task_introduction="You are evaluating an AI-generated software project plan.",
        evaluation_criteria="The plan should: 1) Break the project into logical tasks. "
            "2) Have realistic time estimates. 3) Cover all aspects of the request. "
            "4) Be structured as valid JSON.",
    ),
]

result = evaluate(
    experiment_name="plan-quality-v1",
    dataset=dataset,
    task=plan_generation_task,
    scoring_metrics=metrics,
)
```

---

### 5. Online Evaluation Rules

Four **automated LLM-as-judge rules** are configured via the Opik REST API to run on **every production trace** — no manual experiment needed:

| Rule | Metric | What It Does | Sampling |
|------|--------|-------------|----------|
| **Hallucination Detection** | Custom LLM Judge | Flags fabricated technologies, unrealistic claims, invented capabilities | 100% |
| **Content Safety** | Content Moderation | Checks for offensive language, PII exposure, harmful instructions, bias | 100% |
| **Plan Relevance** | Answer Relevance | Verifies the plan addresses the user's stated goals and context | 100% |
| **Plan Quality** | Domain Expert Judge | Evaluates task decomposition, dependency logic, time estimates, actionability | 100% |

These rules are created programmatically via the Opik REST API:

```python
# backend/setup_online_rules.py
POST https://www.comet.com/opik/api/v1/private/automations/evaluators/
{
    "type": "llm_as_judge",
    "name": "Hallucination Detection",
    "project_ids": ["019c1bb1-..."],
    "sampling_rate": 1.0,
    "enabled": true,
    "action": "evaluator",
    "code": {
        "model": {"name": "gpt-4o-mini", "temperature": 0},
        "messages": [{
            "role": "USER",
            "content": "You are an expert judge... Score: 0.0 = no hallucination, 1.0 = severe...\n\nINPUT:\n{{input}}\n\nOUTPUT:\n{{output}}"
        }],
        "variables": {"input": "input", "output": "output"},
        "schema": [{"name": "hallucination", "type": "DOUBLE", ...}]
    }
}
```

```bash
# One-time setup (idempotent — skips existing rules)
uv run python setup_online_rules.py

# Dry-run to preview without creating
uv run python setup_online_rules.py --dry-run
```

---

### 6. Opik Agent Optimizer

We use the **`opik-optimizer` SDK** (v3.0.1) with `MetaPromptOptimizer` to automatically improve agent system prompts through iterative refinement:

| What's Optimized | Agent | Optimization Metric | Metric Type |
|-----------------|-------|---------------------|-------------|
| Clarification detection prompt | Analyst | JSON structure, question quality, reasoning, alignment with expected traits | Fast heuristic (0 API calls) |
| Plan generation prompt | Architect | Plan structure, task count, required fields, content relevance | Fast heuristic (0 API calls) |

**Why fast heuristic metrics?** The optimizer evaluates many candidate prompts × many dataset samples per trial. LLM-as-judge metrics are too slow and expensive for this inner loop. Our deterministic heuristic metrics return scores in microseconds, enabling the optimizer to explore more of the prompt space:

```python
# backend/optimize_prompts.py
from opik_optimizer import MetaPromptOptimizer, ChatPrompt

prompt = ChatPrompt(
    messages=[
        {"role": "system", "content": ANALYST_INITIAL_PROMPT},
        {"role": "user", "content": "{question}"},
    ],
    model="gemini/gemini-2.5-pro",
)

optimizer = MetaPromptOptimizer(model="gemini/gemini-2.5-pro")

result = optimizer.optimize_prompt(
    prompt=prompt,
    dataset=dataset,              # 12 benchmark items
    metric=analyst_metric,         # Fast heuristic scorer
    max_trials=3,
    n_samples=6,
)
result.display()  # Shows baseline → optimized score progression
```

```bash
# Run optimization
uv run python optimize_prompts.py --agent analyst --trials 3 --samples 6
uv run python optimize_prompts.py --agent architect --trials 3 --samples 6

# Dry-run (no API calls, just shows config)
uv run python optimize_prompts.py --agent analyst --dry-run
```

---

### 7. Experiment Results

#### Plan Quality Experiment (full 6-agent pipeline, 12 samples)

| Metric | Score | Interpretation |
|--------|-------|----------------|
| `plan_structure_completeness` | **1.0000** | All 9 structural fields present in every plan |
| `g_eval_metric` | **0.9833** | Opik's GEval rates plans as excellent |
| `answer_relevance_metric` | **0.9758** | Plans directly address original requests |
| `task_count_reasonableness` | **0.9075** | Task counts match expected ranges for project complexity |
| `duration_realism` | **0.8901** | Realistic time estimates with appropriate buffers |
| `hallucination_metric` | **0.7125** | Some introduced context (expected — plans add suggestions) |
| `plan_quality_llm_judge` | **0.5892** | Conservative holistic judge (strictest metric) |
| `is_json_metric` | **1.0000** | All pipeline outputs are valid JSON |
| `moderation_metric` | **0.0000** | All content is safe (lower = better) |

#### Analyst Experiment (analyst agent only, 12 samples)

| Metric | Score |
|--------|-------|
| `clarification_quality` | **0.6375** |
| `answer_relevance_metric` | **0.6875** |
| `is_json_metric` | **1.0000** |
| `moderation_metric` | **0.0000** |

#### Optimizer Baseline

| Agent | Baseline Score | Metric |
|-------|---------------|--------|
| Analyst | **0.9167** | Fast heuristic (JSON + question quality + reasoning + alignment) |

### Quick Setup

```bash
cd backend

# Required environment variables
export GOOGLE_API_KEY=your_key       # For Gemini models
export OPIK_API_KEY=your_key         # For Opik
export OPIK_WORKSPACE=your_workspace

# Seed the benchmark dataset
uv run python run_evaluation.py --seed

# Run experiments
uv run python run_evaluation.py --experiment plan --name "plan-v1"
uv run python run_evaluation.py --experiment analyst --name "analyst-v1"

# Set up online evaluation rules
uv run python setup_online_rules.py

# Run prompt optimizer
uv run python optimize_prompts.py --agent analyst --trials 3
```

Opik is **completely optional** — if `OPIK_API_KEY` is not set, all tracing and evaluation is silently skipped.

---

## 📚 Technology Stack

### Backend

| Technology | Version | Purpose |
|------------|---------|---------|
| [Python](https://python.org/) | 3.11+ | Runtime |
| [FastAPI](https://fastapi.tiangolo.com/) | 0.115+ | Async web framework with auto-generated OpenAPI docs |
| [Google ADK](https://google.github.io/adk-docs/) | 1.23+ | Agent Development Kit — `LlmAgent`, `Runner`, `InMemorySessionService` |
| [Google GenAI](https://ai.google.dev/) | 1.37+ | Gemini API client — models, Google Search grounding |
| [Pydantic](https://docs.pydantic.dev/) | 2.10+ | Data validation, settings management, agent output schemas |
| [Uvicorn](https://www.uvicorn.org/) | 0.32+ | ASGI server |
| [Opik](https://github.com/comet-ml/opik) | 1.0+ | LLM observability, tracing, evaluation, datasets & experiments |
| [opik-optimizer](https://pypi.org/project/opik-optimizer/) | 3.0+ | Agent prompt optimization (`MetaPromptOptimizer`) |
| [uv](https://docs.astral.sh/uv/) | latest | Fast Python package manager (recommended) |

### Frontend

| Technology | Version | Purpose |
|------------|---------|---------|
| [React](https://react.dev/) | 19 | UI component library |
| [TypeScript](https://www.typescriptlang.org/) | 5.8 | Type-safe JavaScript |
| [Vite](https://vitejs.dev/) | 6 | Build tool & dev server with HMR |
| [TailwindCSS](https://tailwindcss.com/) | (CDN) | Utility-first CSS framework |

---

## 🛠️ Development Guide

### Backend

```bash
cd backend

# Install with dev dependencies
uv sync --extra dev     # or: pip install -e ".[dev]"

# Run with hot reload
uv run uvicorn app.main:app --reload --port 8000

# Code formatting
black app/
isort app/

# Linting
flake8 app/

# Run tests
pytest tests/
```

### Frontend

```bash
cd frontend

# Dev server with hot reload
npm run dev

# Type checking
npx tsc --noEmit

# Production build
npm run build

# Preview production build
npm run preview
```

### Key Development Notes

1. **Agent factories** — All agents are created via factory functions (e.g., `create_architect_agent(critique=None)`). The `critique` parameter enables the retry loop — when a reviewer rejects, the critique is passed back to the agent factory.

2. **Model selection** — `PRO_MODEL` (Gemini 2.5 Pro) is used for agents that need high reasoning (analyst, architect, estimator, manager). `DEFAULT_MODEL` (Gemini 2.5 Flash) is used for reviewers and research — faster and cheaper.

3. **Output schemas** — Each agent has a Pydantic `output_schema` that Google ADK uses to force structured JSON output. The `field_validators` in `output_schemas.py` are critical safety nets for when the LLM returns null values.

4. **Scheduler is deterministic** — Unlike the agents, `scheduler.py` is pure Python (no LLM). It performs topological sort with cycle detection to calculate `startOffset` for each task.

5. **WebSocket is the primary channel** — While REST endpoints exist for `/api/analyze`, `/api/generate`, and `/api/chat`, the main flow uses WebSocket for real-time agent status updates during generation.

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Areas for Improvement

- Extract `App.tsx` into smaller components (chat panel, clarification form)
- Consolidate duplicate schemas (`output_schemas.py` and `models.py` overlap)
- Add comprehensive test coverage
- Add Docker / Docker Compose for one-command setup
- Support for additional LLM providers beyond Gemini

---

## 📄 License

This project is licensed under the Apache 2.0 License — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with ❤️ by [Praveen](https://github.com/Praveen2795)**

[Report Bug](https://github.com/Praveen2795/kanso-ai/issues) · [Request Feature](https://github.com/Praveen2795/kanso-ai/issues)

</div>
