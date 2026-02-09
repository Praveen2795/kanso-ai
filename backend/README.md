# Kanso.AI Backend

AI-powered project planning backend built with FastAPI and a multi-agent system.

## 🔭 Observability with Opik

This project integrates **[Opik](https://github.com/comet-ml/opik)** by Comet for comprehensive AI observability, evaluation, and monitoring.

### Features

- **🔍 Full Trace Visibility**: Track every LLM call across all 6 agents in the pipeline
- **📊 LLM-as-Judge Evaluations**: Automatic quality scoring for generated plans:
  - **Structure Quality**: Logical dependencies, task granularity, phase organization
  - **Estimate Reasonableness**: Realistic durations, appropriate buffers, complexity alignment
  - **Plan Completeness**: Requirement coverage, goal alignment, missing tasks detection
- **💰 Cost & Token Tracking**: Monitor API usage and costs across agent calls
- **⏱️ Performance Metrics**: Latency tracking per agent with detailed timing breakdowns
- **🧪 Experiment Tracking**: Compare model versions and prompt variations

### Setup

1. **Create a Comet account**: [https://www.comet.com/signup](https://www.comet.com/signup) (free tier available)

2. **Get your API credentials** from the Opik settings page

3. **Configure environment variables**:
```bash
OPIK_API_KEY=your_api_key_here
OPIK_WORKSPACE=your_workspace_name
OPIK_PROJECT_NAME=kanso-ai  # Optional, defaults to 'kanso-ai'
```

### Viewing Traces

Once configured, all agent interactions are automatically traced. Visit your Opik dashboard to see:

- **Trace Timeline**: Complete execution flow from user request to final plan
- **Agent Hierarchy**: Nested spans showing Analyst → Architect → Reviewer → Estimator pipeline
- **Evaluation Scores**: Quality metrics for each generated plan
- **Token Usage**: Detailed breakdown per agent and model

### Dashboard URL Pattern
```
https://www.comet.com/opik/{OPIK_WORKSPACE}/kanso-ai/traces
```

---

## Architecture

This backend implements a multi-agent system for intelligent project planning:

```
┌─────────────────────────────────────────────────────────────┐
│                      Orchestrator                            │
│  Coordinates the agent pipeline for plan generation          │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│  Analyst      │    │  Architect    │    │  Estimator    │
│  Agent        │    │  Agent        │    │  Agent        │
│               │    │               │    │               │
│ • Analyzes    │    │ • Creates     │    │ • Bottom-up   │
│   requests    │    │   structure   │    │   estimation  │
│ • Identifies  │    │ • Defines     │    │ • Buffer      │
│   gaps        │    │   phases      │    │   allocation  │
│ • Web search  │    │ • Web search  │    │               │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────┐
                    │  Reviewer     │
                    │  Agent        │
                    │               │
                    │ • Validates   │
                    │   structure   │
                    │ • Validates   │
                    │   estimates   │
                    │ • Final QC    │
                    └───────────────┘
                              │
                              ▼
                    ┌───────────────┐
                    │  Manager      │
                    │  Agent        │
                    │               │
                    │ • Chat        │
                    │   interface   │
                    │ • Plan        │
                    │   refinement  │
                    └───────────────┘
```

## Setup

### Prerequisites

- Python 3.11+
- LLM API Key (see configuration)

### Installation

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -e .
# Or for development:
pip install -e ".[dev]"
```

3. Configure environment:
```bash
cp .env.example .env
# Edit .env and add your API_KEY
```

### Running the Server

```bash
# Development mode with auto-reload
python run.py

# Or using uvicorn directly
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Endpoints

### REST API

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/analyze` | POST | Analyze a project request |
| `/api/generate` | POST | Generate a complete project plan |
| `/api/chat` | POST | Chat with the project manager |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws/{client_id}` | Real-time status updates during generation |

#### WebSocket Actions

```json
// Analyze a request
{"action": "analyze", "topic": "Build a mobile app"}

// Generate a plan
{"action": "generate", "topic": "...", "context": "..."}

// Chat with manager
{"action": "chat", "project": {...}, "message": "...", "history": [...]}

// Keep-alive
{"action": "ping"}
```

## API Documentation

When the server is running, visit:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black app/
isort app/
flake8 app/
```

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   ├── models.py          # Pydantic models
│   ├── main.py            # FastAPI application
│   └── agents/
│       ├── __init__.py
│       ├── analyst.py     # Analyst Agent
│       ├── architect.py   # Architect Agent
│       ├── estimator.py   # Estimator Agent
│       ├── reviewer.py    # Reviewer Agents
│       ├── manager.py     # Project Manager Agent
│       ├── orchestrator.py # Agent pipeline orchestration
       ├── output_schemas.py # Output schemas
│       ├── scheduler.py   # Task scheduling algorithm
│       └── tools.py       # Agent tools
├── tests/
├── .env.example
├── pyproject.toml
├── run.py
└── README.md
```
