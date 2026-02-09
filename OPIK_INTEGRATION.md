# 🔭 Opik Integration — Kanso.AI

## Overview

Kanso.AI is an AI-powered project planning tool that uses a **multi-agent system** (7 specialized agents) built with [Google ADK](https://google.github.io/adk-docs/) to transform any goal into a dependency-aware Gantt chart. **[Opik](https://github.com/comet-ml/opik)** by Comet is deeply integrated across the entire system for observability, evaluation, prompt optimization, and continuous quality improvement.

> **Dashboard**: [https://www.comet.com/opik/praveen170/kanso-ai](https://www.comet.com/opik/praveen170/kanso-ai)

---

## Table of Contents

1. [Full-Pipeline Tracing](#1-full-pipeline-tracing)
2. [Datasets & Experiments](#2-datasets--experiments)
3. [Built-in LLM-as-Judge Metrics](#3-built-in-llm-as-judge-metrics)
4. [Online Evaluation Rules](#4-online-evaluation-rules)
5. [Opik Agent Optimizer](#5-opik-agent-optimizer)
6. [Rich Trace Metadata](#6-rich-trace-metadata)
7. [Architecture](#7-architecture)
8. [Experiment Results](#8-experiment-results)
9. [Running Evaluations](#9-running-evaluations)
10. [Key Files](#10-key-files)

---

## 1. Full-Pipeline Tracing

Every request flows through the multi-agent pipeline with **complete trace visibility** via `OpikTracer` from the official ADK integration:

```
User Request → Analyst → Researcher → Architect → Structure Reviewer
                                                          ↓ (validation loop)
                                                   Estimator → Estimate Reviewer
                                                          ↓ (validation loop)
                                                   Final Reviewer → Scheduler → Gantt Chart
```

**What's Traced** (per request):
- All LLM calls with full input/output payloads
- Agent execution times with millisecond precision
- Token usage per agent (input + output tokens)
- Tool calls (Google Search grounding, web research)
- Validation loop iterations and reviewer decisions
- Error states and retries

**Implementation** (`app/opik_service.py`):
```python
from opik.integrations.adk import OpikTracer

tracer = OpikTracer(
    name="kanso-pipeline",
    tags=["kanso-ai", "project-planning", "multi-agent"],
    metadata={
        "model": "gemini-2.5-pro",
        "judge_model": "gemini-2.5-flash",
        "framework": "google-adk",
    },
    project_name="kanso-ai",
)
```

---

## 2. Datasets & Experiments

A curated **benchmark dataset** (`kanso-planning-benchmark`) with 12 diverse project planning requests is used for systematic evaluation:

| Category | Examples | Purpose |
|----------|----------|---------|
| **Simple/Clear** | Portfolio site, TODO API | Baseline — agent should NOT over-complicate |
| **Moderate/Vague** | E-commerce store, CI/CD pipeline | Should ask clarifications, handle ambiguity |
| **Complex/Enterprise** | Real-time analytics, microservices | Multi-phase with many dependencies |
| **Non-Software** | Podcast launch, home renovation | Domain variety — not just tech |

Each item includes `input`, `context`, `expected_traits` (min/max tasks, expected phases, complexity level), `difficulty`, and `tags`.

**Two experiment types**:

| Experiment | Pipeline | Agents Tested | Metrics |
|------------|----------|---------------|---------|
| **`analyst`** | Analyst only | Clarification detection | 4 metrics (custom + built-in) |
| **`plan`** | Full 6-agent pipeline | End-to-end plan quality | 9 metrics (custom + built-in) |

**Usage**:
```bash
# Seed the benchmark dataset (idempotent)
uv run python run_evaluation.py --seed

# Run experiments
uv run python run_evaluation.py --experiment analyst --name "analyst-v1"
uv run python run_evaluation.py --experiment plan --name "plan-v1"
```

---

## 3. Built-in LLM-as-Judge Metrics

Experiments combine **custom heuristic metrics** with **Opik's built-in LLM-as-judge metrics** (via LiteLLM → Gemini):

### Custom Metrics (deterministic, zero API calls)

| Metric | Type | What It Measures |
|--------|------|------------------|
| `plan_structure_completeness` | Heuristic | All required fields present (title, tasks, phases, deps, subtasks) |
| `task_count_reasonableness` | Heuristic | Task count within expected range for project complexity |
| `duration_realism` | Heuristic | No task < 0.5h or > 80h, buffer ≤ duration |
| `plan_quality_llm_judge` | LLM Judge | Holistic evaluation of requirement coverage, granularity, flow |
| `clarification_quality` | LLM Judge | Analyst correctly identifies ambiguity, asks specific questions |

### Opik Built-in Metrics (LLM-as-judge via `gemini/gemini-2.5-flash`)

| Metric | Built-in Class | What It Measures |
|--------|---------------|------------------|
| `hallucination_metric` | `Hallucination` | Detects fabricated information not grounded in input |
| `answer_relevance_metric` | `AnswerRelevance` | Plan addresses the original request |
| `moderation_metric` | `Moderation` | Content safety check |
| `is_json_metric` | `IsJson` | Pipeline output is valid JSON |
| `g_eval_metric` | `GEval` | Custom criteria: logical tasks, appropriate granularity |

**All 9 metrics run together** in plan experiments, producing a comprehensive quality profile per sample.

---

## 4. Online Evaluation Rules

Four **automated evaluation rules** are configured via the Opik REST API to run on every trace in production — no manual experiment needed:

| Rule | Metric Type | What It Does |
|------|-------------|-------------|
| **Hallucination Detection** | `Hallucination` | Flags traces where the plan contains fabricated information |
| **Content Safety** | `Moderation` | Ensures all outputs pass content safety checks |
| **Plan Relevance** | `AnswerRelevance` | Verifies the plan actually addresses the user's request |
| **Plan Quality** | Custom LLM Judge | Domain-specific evaluation of plan structure and completeness |

All rules use `gpt-4o-mini` as the judge, with 100% trace sampling.

**Setup** (one-time):
```bash
uv run python setup_online_rules.py
```

**Implementation** (`setup_online_rules.py`) uses the Opik REST API:
```python
POST /v1/private/automations/evaluators/
{
    "name": "Hallucination Detection",
    "project_id": "019c1bb1-...",
    "sampling_rate": 1.0,
    "model": { "name": "gpt-4o-mini", "temperature": 0 },
    "code": { "type": "hallucination", ... }
}
```

---

## 5. Opik Agent Optimizer

Uses **`opik-optimizer` SDK** (v3.0.1) with `MetaPromptOptimizer` to automatically improve agent system prompts:

### What Gets Optimized

| Agent | Prompt Optimized | Metric | Goal |
|-------|-----------------|--------|------|
| **Analyst** | System prompt for clarification detection | Fast heuristic (JSON structure, question quality, reasoning, alignment) | Better ambiguity detection |
| **Architect** | System prompt for plan generation | Fast heuristic (plan structure, task count, required fields, relevance) | Better plan quality |

### How It Works

1. **Dataset**: Uses the benchmark dataset items as optimization training data
2. **Prompt Template**: `ChatPrompt` with system + user messages, template variable `{question}`
3. **MetaPromptOptimizer**: Uses an LLM "reasoning model" to critique and iteratively refine the prompt
4. **Fast Metrics**: Deterministic heuristic scoring (zero API calls) — enables rapid iteration across many trials

```bash
# Dry-run to see configuration
uv run python optimize_prompts.py --agent analyst --dry-run

# Run optimization (3 trials, 4 samples each)
uv run python optimize_prompts.py --agent analyst --trials 3 --samples 4

# Architect optimization
uv run python optimize_prompts.py --agent architect --trials 3 --samples 6
```

### Design Decision: Fast Heuristic Metrics

The optimizer metrics are intentionally **lightweight and deterministic** (no LLM API calls). This was critical because:

- The optimizer evaluates many candidates × many samples per trial
- LLM-as-judge metrics are too slow and expensive for optimization loops
- Deterministic metrics prevent the optimizer from chasing noise
- This follows Opik's own [metric design guidelines](https://www.comet.com/docs/opik/agent_optimization/optimization/define_metrics)

---

## 6. Rich Trace Metadata

Every trace is enriched with detailed metadata beyond basic LLM input/output:

### Pipeline-Level Metadata (on `generate_project_plan` traces)

| Field | Type | Description |
|-------|------|-------------|
| `pipeline_elapsed_seconds` | float | Total wall-clock time for the entire pipeline |
| `stage_timings` | dict | Per-stage timing: architecture, estimation, finalize |
| `architecture_iterations` | int | How many times the architect was asked to revise |
| `estimation_iterations` | int | How many times the estimator was asked to revise |
| `structure_validated` | bool | Did the structure pass review? |
| `estimates_validated` | bool | Did the estimates pass review? |
| `complexity_distribution` | dict | Count of Low/Medium/High complexity tasks |
| `has_research_context` | bool | Whether web research was used |

### Agent-Level Metadata (per-span via `opik_context.update_current_span()`)

| Field | Type | Description |
|-------|------|-------------|
| `agent_name` | string | Which agent (analyst, architect, estimator, etc.) |
| `agent_type` | string | `pro_model` or `default_model` |
| `execution_time_ms` | float | Agent execution time in milliseconds |
| `response_length` | int | Character count of agent response |
| `model` | string | Model name (e.g., `gemini-2.5-pro`) |

### Function-Level Metadata

| Function | Tracked Fields |
|----------|---------------|
| `analyze_request` | topic_length, has_chat_history, needs_clarification, question_count, elapsed_seconds |
| `chat_with_manager` | message_length, history_turns, project_task_count, has_plan_update, reply_length, elapsed_seconds |

---

## 7. Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                           Kanso.AI Backend                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────┐    ┌───────────────┐    ┌────────────────────────┐    │
│  │   FastAPI     │───▶│ Orchestrator  │───▶│   Google ADK Agents    │    │
│  │   Server      │    │   Pipeline    │    │   (7 agents)           │    │
│  └──────────────┘    └───────┬───────┘    └──────────┬─────────────┘    │
│                              │                        │                   │
│                     ┌────────▼────────────────────────▼──────────────┐   │
│                     │              Opik Integration                    │   │
│                     │                                                 │   │
│                     │  ┌──────────┐  ┌──────────────┐  ┌──────────┐ │   │
│                     │  │ Tracing  │  │ Evaluations  │  │ Online   │ │   │
│                     │  │ (ADK     │  │ (Datasets,   │  │ Rules    │ │   │
│                     │  │  Tracer) │  │  Experiments,│  │ (Auto    │ │   │
│                     │  │          │  │  9 Metrics)  │  │  Eval)   │ │   │
│                     │  └──────────┘  └──────────────┘  └──────────┘ │   │
│                     │                                                 │   │
│                     │  ┌──────────────────┐  ┌─────────────────────┐ │   │
│                     │  │ Agent Optimizer  │  │  Rich Metadata      │ │   │
│                     │  │ (MetaPrompt,     │  │  (Pipeline timing,  │ │   │
│                     │  │  Fast Metrics)   │  │   Per-agent spans)  │ │   │
│                     │  └──────────────────┘  └─────────────────────┘ │   │
│                     └─────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
                        ┌───────────────────────┐
                        │   Comet.com / Opik     │
                        │   Dashboard            │
                        │   - Trace Timeline     │
                        │   - Experiments         │
                        │   - Optimization Runs   │
                        │   - Online Eval Rules   │
                        │   - Cost Analysis       │
                        └───────────────────────┘
```

---

## 8. Experiment Results

### Plan Quality Experiment (`plan-builtin-metrics-v2`)

12 samples evaluated through the full 6-agent pipeline:

| Metric | Score | Interpretation |
|--------|-------|----------------|
| `plan_structure_completeness` | **1.0000** | All structural fields present in every plan |
| `g_eval_metric` | **0.9833** | LLM judge rates plans as excellent |
| `answer_relevance_metric` | **0.9758** | Plans directly address user requests |
| `task_count_reasonableness` | **0.9075** | Task counts match expected ranges |
| `duration_realism` | **0.8901** | Realistic time estimates |
| `hallucination_metric` | **0.7125** | Some introduced context (expected for plans) |
| `plan_quality_llm_judge` | **0.5892** | Conservative holistic judge |
| `is_json_metric` | **1.0000** | All outputs are valid JSON |
| `moderation_metric` | **0.0000** | All content is safe (lower = better) |

### Analyst Experiment (`analyst-builtin-metrics-v2`)

12 samples evaluated for clarification quality:

| Metric | Score |
|--------|-------|
| `clarification_quality` | **0.6375** |
| `answer_relevance_metric` | **0.6875** |
| `is_json_metric` | **1.0000** |
| `moderation_metric` | **0.0000** |

### Optimizer Baseline

| Agent | Baseline Score | Status |
|-------|---------------|--------|
| Analyst | **0.9167** | Optimization complete |

---

## 9. Running Evaluations

### Prerequisites

```bash
cd backend

# Required environment variables
export GOOGLE_API_KEY=your_google_api_key    # For Gemini models
export OPIK_API_KEY=your_opik_api_key        # For Opik
export OPIK_WORKSPACE=your_workspace_name
```

### Commands

```bash
# Seed the benchmark dataset (idempotent, run once)
uv run python run_evaluation.py --seed

# Run analyst experiment (clarification quality)
uv run python run_evaluation.py --experiment analyst --name "my-analyst-test"

# Run plan experiment (full pipeline, ~6 min for 12 samples)
uv run python run_evaluation.py --experiment plan --name "my-plan-test"

# Set up online evaluation rules (one-time)
uv run python setup_online_rules.py

# Run prompt optimization
uv run python optimize_prompts.py --agent analyst --trials 3 --samples 4
uv run python optimize_prompts.py --agent architect --trials 3 --samples 6

# Dry-run optimizer (no API calls)
uv run python optimize_prompts.py --agent analyst --dry-run
```

---

## 10. Key Files

| File | Lines | Purpose |
|------|-------|---------|
| [`app/opik_service.py`](backend/app/opik_service.py) | ~925 | Core Opik integration: tracing, ADK tracer, dataset management, experiment runner |
| [`app/evaluation.py`](backend/app/evaluation.py) | ~903 | Evaluation framework: benchmark dataset, 5 custom metrics, 5 built-in metrics, experiment task functions |
| [`app/agents/orchestrator.py`](backend/app/agents/orchestrator.py) | ~893 | Agent pipeline with rich Opik trace metadata (timing, iterations, spans) |
| [`run_evaluation.py`](backend/run_evaluation.py) | ~179 | CLI entry point: seed datasets, run experiments |
| [`setup_online_rules.py`](backend/setup_online_rules.py) | ~280 | Opik REST API: automated LLM-as-judge evaluation rules |
| [`optimize_prompts.py`](backend/optimize_prompts.py) | ~450 | Opik Agent Optimizer: MetaPromptOptimizer with fast heuristic metrics |

---

## Hackathon Alignment: "Best Use of Opik"

| Opik Feature | Implementation | Depth |
|-------------|----------------|-------|
| **Tracing** | Full ADK pipeline tracing with OpikTracer, recursive agent instrumentation | ⭐⭐⭐ |
| **Datasets** | Curated 12-item benchmark with expected_traits, difficulty, tags | ⭐⭐⭐ |
| **Experiments** | Two experiment types (analyst + plan) with named runs, reproducible | ⭐⭐⭐ |
| **Built-in Metrics** | Hallucination, AnswerRelevance, Moderation, GEval, IsJson — all via Gemini | ⭐⭐⭐ |
| **Custom Metrics** | 5 domain-specific metrics (heuristic + LLM-as-judge) | ⭐⭐⭐ |
| **Online Eval Rules** | 4 automated rules via REST API with 100% sampling | ⭐⭐⭐ |
| **Agent Optimizer** | MetaPromptOptimizer for analyst + architect prompts with fast metrics | ⭐⭐⭐ |
| **Rich Metadata** | Pipeline timing, iteration counts, per-agent spans, complexity distribution | ⭐⭐⭐ |
| **Cost Tracking** | Token usage per agent via OpikTracer | ⭐⭐ |

---

*Built for the [Commit To Change: An AI Agents Hackathon](https://www.encodeclub.com/programmes/comet-resolution-v2-hackathon) by Encode Club × Comet.*
