# Kanso.AI Backend

AI-powered project planning backend built with FastAPI and Google ADK multi-agent system.

## Architecture

This backend implements a multi-agent system using Google's Agent Development Kit (ADK):

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
- Google API Key with Gemini access

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
# Edit .env and add your GOOGLE_API_KEY
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
│       ├── schemas.py     # Gemini output schemas
│       ├── scheduler.py   # Task scheduling algorithm
│       └── tools.py       # Agent tools
├── tests/
├── .env.example
├── pyproject.toml
├── run.py
└── README.md
```
