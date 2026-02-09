# 🔭 Opik Observability Integration - Kanso.AI

## Overview

Kanso.AI is an AI-powered project planning tool that uses a **multi-agent system** built with Google's Agent Development Kit (ADK). The system orchestrates 6 specialized AI agents to generate comprehensive project plans.

This document explains how **Opik** by Comet is deeply integrated for observability, evaluation, and continuous improvement.

> **Note**: This integration follows patterns established in [commit-coach](https://github.com/Praveen2795/commit-coach), ensuring consistency across projects.

---

## 🎯 Key Opik Integration Features

### 1. **Full Agent Pipeline Tracing**

Every request flows through our multi-agent pipeline with complete visibility:

```
User Request → Analyst → Researcher → Architect → Reviewer → Estimator → Manager
                 ↑                                              ↓
              Opik traces every LLM call, tool use, and decision
```

**What's Traced:**
- All LLM calls with input/output
- Agent execution times
- Token usage per agent
- Tool calls (Google Search for research)
- Error states and retries

### 2. **LLM-as-Judge Online Evaluations**

After every plan generation, Opik runs **3 automatic quality evaluations**:

| Metric | What It Measures | Weight |
|--------|------------------|--------|
| **Plan Structure Score** | Logical dependencies, task granularity, phase organization | 30% |
| **Estimate Reasonableness** | Realistic durations, appropriate buffers, complexity alignment | 30% |
| **Plan Completeness** | Requirement coverage, goal alignment, missing tasks detection | 40% |

These scores are automatically logged to each trace for:
- Quality monitoring over time
- Identifying regression in model performance
- A/B testing different prompt strategies

### 3. **Google ADK Integration**

Kanso.AI uses `OpikTracer` from the official Opik ADK integration:

```python
from opik.integrations.adk import OpikTracer, track_adk_agent_recursive

# Create tracer with metadata
tracer = OpikTracer(
    name="kanso-analyst-agent",
    tags=["kanso-ai", "project-planning", "multi-agent"],
    metadata={
        "environment": "production",
        "model": "gemini-2.5-pro",
        "framework": "google-adk"
    },
    project_name="kanso-ai"
)

# Instrument all agents recursively
track_adk_agent_recursive(agent, tracer)
```

### 4. **Tracking Decorators (commit-coach Pattern)**

Following the established patterns from commit-coach:

```python
from opik_service import track_agent_run, track_tool_call

@track_agent_run(agent_name="architect")
async def create_project_structure():
    # Automatically tracks:
    # - Agent name and model
    # - Framework (google-adk)
    # - Execution span
    pass

@track_tool_call(tool_name="google_search")
def search_web(query: str):
    # Tracks tool calls separately
    pass
```

### 5. **Agent Callbacks**

Before/after callbacks for detailed tracing:

```python
from opik_service import opik_before_agent_callback, opik_after_agent_callback

# Before agent runs
opik_before_agent_callback(
    agent_name="architect",
    invocation_context={"topic": "AI project"}
)

# After agent completes
opik_after_agent_callback(
    agent_name="architect",
    result="Generated structure with 5 phases"
)
```

### 6. **User Feedback Collection**

Users can rate generated plans, which feeds back into Opik:

```
POST /api/feedback
{
    "trace_id": "abc123",
    "score": 0.85,
    "category": "user_satisfaction",
    "comment": "Great plan but missing security phase"
}
```

This creates a feedback loop for:
- Identifying low-quality outputs
- Correlating user satisfaction with evaluation scores
- Improving prompts based on real feedback

### 7. **Trace Flushing**

Traces are automatically flushed:
- After each plan generation
- On application shutdown

```python
from opik_service import flush_traces

# Ensure all traces are sent to Opik
flush_traces()
```

---

## 📊 Opik Dashboard Insights

### Trace View
See the complete execution flow of any plan generation:
- Nested spans for each agent
- Token counts and costs
- Input/output for every LLM call
- Tool calls (Google Search, etc.)

### Evaluation Trends
Track quality over time:
- Average quality scores per day
- Score distributions
- Identification of degradation

### Cost Analysis
Monitor API spending:
- Cost per plan generation
- Cost breakdown by agent
- Token usage optimization opportunities

---

## 🏗️ Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        Kanso.AI Backend                           │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   FastAPI   │───▶│ Orchestrator│───▶│ Google ADK Agents   │  │
│  │   Server    │    │   Layer     │    │ (Analyst, Architect │  │
│  └─────────────┘    └──────┬──────┘    │  Estimator, etc.)   │  │
│                            │           └─────────────────────┘  │
│                            │                      │              │
│                            ▼                      ▼              │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    Opik Observability                       │ │
│  │  ┌──────────┐  ┌──────────────┐  ┌─────────────────────┐  │ │
│  │  │ Tracing  │  │ Evaluations  │  │ Feedback Collection │  │ │
│  │  │ (ADK)    │  │ (LLM Judge)  │  │ (User Ratings)      │  │ │
│  │  └──────────┘  └──────────────┘  └─────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
                                │
                                ▼
                    ┌───────────────────────┐
                    │   Comet.com Opik      │
                    │   Dashboard           │
                    │   - Trace Viewer      │
                    │   - Evaluation Charts │
                    │   - Cost Analysis     │
                    └───────────────────────┘
```

---

## 🚀 Getting Started

### 1. Set Up Opik Account
Create a free account at [https://www.comet.com/signup](https://www.comet.com/signup)

### 2. Configure Environment
```bash
# In backend/.env
OPIK_API_KEY=your_api_key
OPIK_WORKSPACE=your_workspace
OPIK_PROJECT_NAME=kanso-ai
```

### 3. Start the Server
```bash
cd backend
pip install -e .
python run.py
```

### 4. View Dashboard
Navigate to:
```
https://www.comet.com/opik/{your_workspace}/kanso-ai/traces
```

---

## 📈 Hackathon Criteria Alignment

| Criteria | Implementation |
|----------|----------------|
| **Functionality** | ✅ Multi-agent system with 6 specialized agents |
| **Real-world relevance** | ✅ Project planning tool for developers and teams |
| **Use of LLMs/Agents** | ✅ Google ADK with Gemini models, tool use (search) |
| **Evaluation & Observability** | ✅ Full Opik integration with LLM-as-judge |
| **Goal Alignment** | ✅ Traces, evaluations, feedback loop, dashboards |

---

## 🔗 Key Files

| File | Purpose |
|------|---------|
| `app/opik_service.py` | Opik configuration, tracing decorators, callbacks, custom metrics |
| `app/agents/orchestrator.py` | Agent pipeline with @track decorators and flush_traces() |
| `app/main.py` | API endpoints including feedback, lifecycle trace flushing |
| `app/config.py` | Environment configuration |

### opik_service.py Functions

```python
# Configuration
configure_opik()           # Initialize Opik with credentials
flush_traces()             # Flush pending traces to Opik
is_opik_enabled()          # Check if Opik is available

# Tracing Decorators
track_agent_run(agent_name)  # Decorator for agent functions
track_tool_call(tool_name)   # Decorator for tool functions

# Callbacks
opik_before_agent_callback(agent_name, context)  # Pre-agent callback
opik_after_agent_callback(agent_name, result)    # Post-agent callback

# ADK Integration
create_adk_tracer(name, tags, metadata)  # Create OpikTracer
instrument_agent(agent, tracer)          # Instrument ADK agent

# Feedback & URLs
log_feedback(trace_id, score, category, comment)
log_agent_feedback(trace_id, score, feedback_type, comment)
get_trace_url(trace_id)
get_dashboard_url()
```

---

## 📝 Notes for Judges

1. **Traces are available in real-time** - Generate a plan and see it appear in the dashboard immediately

2. **LLM-as-judge evaluations run automatically** - No manual intervention needed

3. **Feedback loop is functional** - Rate any plan and see it reflected in trace metadata

4. **Cost tracking is built-in** - Token usage and estimated costs per request

5. **Pattern consistency** - Follows same patterns as [commit-coach](https://github.com/Praveen2795/commit-coach) for production-ready observability

Feel free to explore the Opik dashboard to see the full observability capabilities in action!
