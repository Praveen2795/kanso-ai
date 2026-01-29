# Kanso.AI Frontend

React-based frontend for the AI-powered project planning application.

## Setup

### Prerequisites

- Node.js 18+
- Backend server running (see `../backend/README.md`)

### Installation

1. Install dependencies:
```bash
npm install
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env if needed (defaults work for local development)
```

### Development

```bash
npm run dev
```

The app will be available at `http://localhost:5173`

### Production Build

```bash
npm run build
npm run preview
```

## Project Structure

```
frontend/
├── App.tsx              # Main application component
├── index.tsx            # Entry point
├── index.html           # HTML template
├── types.ts             # TypeScript type definitions
├── components/
│   ├── AgentStatusDisplay.tsx  # Agent activity indicator
│   ├── GanttChart.tsx          # Interactive Gantt chart
│   ├── ImpactBackground.tsx    # Animated background
│   └── ProjectDetails.tsx      # Project details view
├── services/
│   └── apiService.ts    # API client & WebSocket service
├── package.json
├── tsconfig.json
└── vite.config.ts
```

## Features

- **Real-time Agent Status**: WebSocket connection shows agent activity during plan generation
- **Interactive Gantt Chart**: Visualize project timeline with dependencies
- **Project Details View**: Expandable task tree with subtasks
- **Chat Interface**: Refine plans through conversation with the Project Manager agent
- **File Upload**: Attach reference documents for context
- **Responsive Design**: Works on desktop and mobile

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `VITE_API_URL` | Backend REST API URL | `http://localhost:8000` |
| `VITE_WS_URL` | Backend WebSocket URL | `ws://localhost:8000` |

## API Integration

The frontend communicates with the backend via:

1. **REST API** - For simple requests (health check, one-off operations)
2. **WebSocket** - For real-time status updates during plan generation

See [apiService.ts](services/apiService.ts) for implementation details.
