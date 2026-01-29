# Kanso.AI - AI-Powered Project Planning

<div align="center">

**Transform any goal into a detailed, actionable project plan with AI**

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](https://react.dev)
[![License](https://img.shields.io/badge/License-Apache_2.0-green.svg)](LICENSE)

</div>

---

## 🎯 What is Kanso.AI?

Kanso.AI is an intelligent project planning application that uses a **multi-agent AI system** to:

1. **Analyze** your project idea and ask clarifying questions
2. **Design** a structured breakdown (Phases → Tasks → Subtasks)
3. **Estimate** realistic timelines with complexity-based buffers
4. **Validate** the plan through multiple review cycles
5. **Refine** the schedule through natural conversation

Whether you're planning a startup launch, a home renovation, a study schedule, or a wedding — Kanso.AI turns your goal into a detailed Gantt chart you can actually follow.

---

## ✨ Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **Multi-Agent Pipeline** | 5 specialized AI agents collaborate to create and refine your plan |
| 📊 **Interactive Gantt Chart** | Visualize your project timeline with phases, dependencies, and milestones |
| 💬 **Conversational Refinement** | Chat with the Project Manager to adjust tasks, timelines, and scope |
| 📎 **File Upload Support** | Attach reference documents to provide additional context |
| ⚡ **Real-time Updates** | WebSocket connection shows live agent status as your plan is built |
| 🎨 **Beautiful UI** | Clean, responsive interface with smooth animations |

---

## 🏗️ Architecture Overview

Kanso.AI follows a clean **frontend/backend separation** with a Python-based multi-agent system:

```
kanso-ai/
├── frontend/                    # React + TypeScript + Vite
│   ├── App.tsx                  # Main application component
│   ├── types.ts                 # TypeScript type definitions
│   ├── components/
│   │   ├── AgentStatusDisplay   # Shows active agent progress
│   │   ├── GanttChart           # Interactive timeline visualization
│   │   ├── ProjectDetails       # Task details & assumptions
│   │   └── ImpactBackground     # Animated background effects
│   └── services/
│       └── apiService.ts        # REST API & WebSocket client
│
├── backend/                     # FastAPI + Python
│   ├── run.py                   # Server entry point
│   ├── pyproject.toml           # Python dependencies
│   └── app/
│       ├── main.py              # FastAPI application & routes
│       ├── models.py            # Pydantic data models
│       ├── config.py            # Environment configuration
│       └── agents/              # Multi-agent system
│           ├── orchestrator.py  # Agent pipeline coordinator
│           ├── analyst.py       # Request analysis agent
│           ├── architect.py     # Structure design agent
│           ├── estimator.py     # Time estimation agent
│           ├── reviewer.py      # Validation agents
│           ├── manager.py       # Chat refinement agent
│           ├── scheduler.py     # Dependency-aware scheduling
│           ├── output_schemas.py# Pydantic schemas for agent outputs
│           └── tools.py         # Shared agent tools
│
└── README.md
```

---

## 🤖 Multi-Agent System

The heart of Kanso.AI is a **collaborative multi-agent workflow**. Each agent has a specialized role:

### Agent Roles

| Agent | Responsibility |
|-------|----------------|
| **Analyst** | Analyzes user requests, identifies ambiguities, asks clarifying questions |
| **Architect** | Designs project structure: phases, tasks, subtasks, and dependencies |
| **Structure Reviewer** | Validates logical dependencies and structural completeness |
| **Estimator** | Bottom-up time estimation with complexity-based buffer allocation |
| **Estimate Reviewer** | Sanity-checks time estimates and buffer percentages |
| **Final Reviewer** | Polishes output format and ensures consistency |
| **Manager** | Handles conversational refinements to the plan |

### Agent Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        USER INPUT                               │
│              "Plan a 2-week Japan itinerary"                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    🔍 ANALYST AGENT                             │
│  • Analyzes the request for completeness                        │
│  • Identifies missing information                               │
│  • Returns clarifying questions (if needed)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │ Questions?        │                   │ Ready
          ▼                   │                   ▼
    ┌───────────┐             │         ┌─────────────────────────┐
    │  User     │◄────────────┘         │  🏛️ ARCHITECT AGENT    │
    │  Answers  │                       │  • Creates phases        │
    └───────────┘                       │  • Defines tasks         │
          │                             │  • Maps dependencies     │
          └────────────────────────────►└─────────────────────────┘
                                                  │
                                                  ▼
                              ┌─────────────────────────────────────┐
                              │      🔄 STRUCTURE REVIEWER          │
                              │  • Validates dependencies           │
                              │  • Checks completeness              │
                              │  • Returns critique (if invalid)    │
                              └─────────────────────────────────────┘
                                                  │
                         ┌────────────────────────┼─────────┐
                         │ Invalid (retry)        │         │ Valid
                         ▼                        │         ▼
                    ┌─────────┐                   │  ┌─────────────────────────┐
                    │Architect│◄──────────────────┘  │  ⏱️ ESTIMATOR AGENT    │
                    │ (retry) │                      │  • Bottom-up estimates   │
                    └─────────┘                      │  • Complexity analysis   │
                                                     │  • Buffer allocation     │
                                                     └─────────────────────────┘
                                                               │
                                                               ▼
                                         ┌─────────────────────────────────────┐
                                         │      🔄 ESTIMATE REVIEWER           │
                                         │  • Sanity-checks durations          │
                                         │  • Validates buffer percentages     │
                                         │  • Returns critique (if invalid)    │
                                         └─────────────────────────────────────┘
                                                               │
                                    ┌──────────────────────────┼─────────┐
                                    │ Invalid (retry)          │         │ Valid
                                    ▼                          │         ▼
                               ┌──────────┐                    │  ┌─────────────────────────┐
                               │Estimator │◄───────────────────┘  │  ✨ FINAL REVIEWER      │
                               │ (retry)  │                       │  • Polishes output       │
                               └──────────┘                       │  • Ensures consistency   │
                                                                  └─────────────────────────┘
                                                                            │
                                                                            ▼
                              ┌─────────────────────────────────────────────────────────────┐
                              │                    📊 SCHEDULER                             │
                              │  • Calculates startOffset based on dependencies            │
                              │  • Resolves parallel vs sequential tasks                   │
                              │  • Computes total project duration                         │
                              └─────────────────────────────────────────────────────────────┘
                                                                            │
                                                                            ▼
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              📈 GANTT CHART                                             │
│  Interactive visualization of your project plan                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
                                                                            │
                                                                            ▼
                              ┌─────────────────────────────────────────────────────────────┐
                              │                   💬 MANAGER AGENT                          │
                              │  "Make the trip shorter" → Updates plan                    │
                              │  "Add a day in Osaka" → Adds new tasks                     │
                              │  "What's on day 3?" → Explains schedule                    │
                              └─────────────────────────────────────────────────────────────┘
```

### Validation Loops

The pipeline includes **built-in quality control**:

- If the Structure Reviewer finds issues (missing dependencies, incomplete tasks), the Architect is asked to revise
- If the Estimate Reviewer finds issues (unrealistic times, missing buffers), the Estimator is asked to recalculate
- This ensures higher quality output without requiring user intervention

### Smart Task Merging

When the Manager agent updates the plan during chat, a **merge strategy** preserves existing task data:

- Partial updates are merged with original tasks (preserving duration, buffer, subtasks)
- New tasks are added with unique IDs
- Deleted tasks are removed
- This prevents the Gantt chart from breaking due to incomplete LLM responses

---

## 🚀 Getting Started

### Prerequisites

- **Python 3.11+** 
- **Node.js 18+**
- **LLM API Key** (see configuration)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/kanso-ai.git
cd kanso-ai
```

### 2. Set Up the Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -e .

# Configure environment
cp .env.example .env
```

Edit `backend/.env` and add your API key:

```env
API_KEY=your_api_key_here
```

Start the backend server:

```bash
python run.py
```

The API will be available at `http://localhost:8000`

### 3. Set Up the Frontend

```bash
cd frontend

# Install dependencies
npm install

# (Optional) Configure environment
cp .env.example .env

# Start development server
npm run dev
```

The app will be available at `http://localhost:3000`

---

## 📡 API Reference

### REST Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/analyze` | POST | Analyze a project request, returns clarifying questions |
| `/api/generate` | POST | Generate complete project plan |
| `/api/chat` | POST | Chat with the project manager to refine the plan |

### WebSocket

| Endpoint | Description |
|----------|-------------|
| `/ws/{client_id}` | Real-time agent status updates during plan generation |

### Example: Generate a Plan

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d '{
    "topic": "Launch a Shopify store in 30 days",
    "context": "Budget is $5000, selling handmade jewelry",
    "clientId": "my-client-123"
  }'
```

---

## ⚙️ Configuration

### Backend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `API_KEY` | LLM API Key | **Required** |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8000` |
| `CORS_ORIGINS` | Allowed CORS origins | `http://localhost:5173,http://localhost:3000` |
| `DEFAULT_MODEL` | Fast model for reviewers | (configured in backend) |
| `PRO_MODEL` | Pro model for complex tasks | (configured in backend) |

### Frontend Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend REST API URL | `http://localhost:8000` |
| `VITE_WS_URL` | Backend WebSocket URL | `ws://localhost:8000` |

---

## 🛠️ Development

### Backend Development

```bash
cd backend
source venv/bin/activate

# Install dev dependencies
pip install -e ".[dev]"

# Run with hot reload
uvicorn app.main:app --reload --port 8000

# Code formatting
black app/
isort app/

# Linting
flake8 app/
```

### Frontend Development

```bash
cd frontend

# Development server with hot reload
npm run dev

# Type checking
npx tsc --noEmit

# Production build
npm run build
```

---

## 📚 Technology Stack

### Backend
| Technology | Purpose |
|------------|---------|
| [FastAPI](https://fastapi.tiangolo.com/) | High-performance Python web framework |

| [Pydantic](https://docs.pydantic.dev/) | Data validation and serialization |
| [Uvicorn](https://www.uvicorn.org/) | ASGI server |

### Frontend
| Technology | Purpose |
|------------|---------|
| [React 19](https://react.dev/) | UI component library |
| [TypeScript](https://www.typescriptlang.org/) | Type-safe JavaScript |
| [Vite](https://vitejs.dev/) | Fast build tool and dev server |
| [TailwindCSS](https://tailwindcss.com/) | Utility-first CSS framework |

---

## 🗂️ Project Structure Deep Dive

### Backend Agents (`backend/app/agents/`)

| File | Description |
|------|-------------|
| `orchestrator.py` | Main coordinator - runs the agent pipeline, handles task merging |
| `analyst.py` | Analyzes requests and generates clarifying questions |
| `architect.py` | Creates project structure with phases, tasks, and dependencies |
| `estimator.py` | Calculates time estimates using bottom-up estimation |
| `reviewer.py` | Three reviewers: structure, estimates, and final cleanup |
| `manager.py` | Handles chat-based refinements to the plan |
| `scheduler.py` | Calculates `startOffset` based on task dependencies |
| `output_schemas.py` | Pydantic models that define agent output structure |
| `tools.py` | Shared utilities (e.g., `get_current_date()`) |

### Frontend Components (`frontend/components/`)

| Component | Description |
|-----------|-------------|
| `AgentStatusDisplay` | Shows which agent is currently working with animated progress |
| `GanttChart` | Interactive timeline visualization with phases and task bars |
| `ProjectDetails` | Expandable view of tasks, subtasks, and assumptions |
| `ImpactBackground` | Animated background effect for visual polish |

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the Apache 2.0 License - see the [LICENSE](LICENSE) file for details.

---

<div align="center">

**Built with ❤️**

[Report Bug](https://github.com/yourusername/kanso-ai/issues) · [Request Feature](https://github.com/yourusername/kanso-ai/issues)

</div>
