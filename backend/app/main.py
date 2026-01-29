"""
FastAPI application with REST API endpoints and WebSocket support.
"""

import json
import asyncio
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from .config import get_settings
from .models import (
    AnalyzeRequest, AnalysisResponse,
    GeneratePlanRequest, PlanGenerationResult,
    ChatRequest, ChatResponse,
    ProjectData, AgentStatusUpdate,
    CalendarExportRequest
)
from .agents.orchestrator import (
    analyze_request,
    generate_project_plan,
    chat_with_manager
)
from .calendar_export import generate_ics

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    print(f"🚀 Kanso.AI Backend starting on {settings.host}:{settings.port}")
    yield
    # Shutdown
    print("👋 Kanso.AI Backend shutting down")


app = FastAPI(
    title="Kanso.AI API",
    description="AI-powered project planning with multi-agent system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# WebSocket connection manager for real-time status updates
class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
    
    async def send_status(self, client_id: str, status: AgentStatusUpdate):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(
                    status.model_dump(by_alias=True)
                )
            except Exception:
                self.disconnect(client_id)


manager = ConnectionManager()


# --- REST API Endpoints ---

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "kanso-ai-backend"}


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_project_request(request: AnalyzeRequest):
    """
    Analyze a project request and determine if clarification is needed.
    
    This runs the Analyst Agent to:
    - Verify technical terms
    - Check URL accessibility
    - Identify missing context
    """
    try:
        result = await analyze_request(
            topic=request.topic,
            chat_history=request.chat_history
        )
        
        return AnalysisResponse(
            needsClarification=result.get("needsClarification", False),
            questions=result.get("questions", []),
            reasoning=result.get("reasoning", "")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/generate", response_model=PlanGenerationResult)
async def generate_plan(request: GeneratePlanRequest):
    """
    Generate a complete project plan.
    
    This runs the full agent pipeline:
    1. Architect creates structure
    2. Reviewer validates structure
    3. Estimator calculates times
    4. Reviewer validates estimates
    5. Final cleanup and scheduling
    
    For real-time status updates, use the WebSocket endpoint.
    """
    try:
        project = await generate_project_plan(
            topic=request.topic,
            context=request.context,
            file=request.file
        )
        
        return PlanGenerationResult(
            project=project,
            success=True
        )
    except Exception as e:
        return PlanGenerationResult(
            project=ProjectData(title="", description="", tasks=[]),
            success=False,
            error=str(e)
        )


@app.post("/api/chat", response_model=ChatResponse)
async def chat_with_project(request: ChatRequest):
    """
    Chat with the Project Manager agent to refine the plan.
    
    The manager can:
    - Add/remove/modify tasks
    - Adjust timelines
    - Explain the schedule
    - Answer project-specific questions
    """
    try:
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.history
        ]
        
        result = await chat_with_manager(
            project=request.project,
            message=request.message,
            history=history
        )
        
        updated_plan = None
        if result.get("updatedPlan"):
            # Convert back to ProjectData
            plan_data = result["updatedPlan"]
            from .agents.orchestrator import parse_tasks_from_plan
            tasks = parse_tasks_from_plan(plan_data)
            
            updated_plan = ProjectData(
                title=plan_data.get("projectTitle", request.project.title),
                description=plan_data.get("projectSummary", request.project.description),
                assumptions=plan_data.get("assumptions", []),
                tasks=tasks,
                totalDuration=plan_data.get("totalDuration", 0)
            )
        
        return ChatResponse(
            reply=result.get("reply", "I couldn't process that request."),
            updatedPlan=updated_plan
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export/calendar")
async def export_to_calendar(request: CalendarExportRequest):
    """
    Export project plan as an ICS (iCalendar) file.
    
    The generated file can be imported into:
    - Google Calendar
    - Microsoft Outlook
    - Apple Calendar
    - Any iCalendar-compatible application
    
    The export creates calendar events for each task, blocking time
    appropriately so users can see their workload.
    """
    try:
        # Parse start date if provided
        start_date = None
        if request.start_date:
            try:
                start_date = datetime.fromisoformat(request.start_date)
                start_date = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
            except ValueError:
                raise HTTPException(
                    status_code=400, 
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        
        # Determine working days
        working_days = [0, 1, 2, 3, 4]  # Mon-Fri
        if request.include_weekends:
            working_days = [0, 1, 2, 3, 4, 5, 6]  # All days
        
        # Generate ICS content
        ics_content = generate_ics(
            project=request.project,
            start_date=start_date,
            hours_per_day=request.hours_per_day,
            working_days=working_days
        )
        
        # Create safe filename
        safe_title = "".join(c if c.isalnum() or c in " -_" else "" for c in request.project.title)
        safe_title = safe_title[:50].strip() or "project"
        filename = f"{safe_title.replace(' ', '_')}_plan.ics"
        
        return Response(
            content=ics_content,
            media_type="text/calendar",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# --- WebSocket Endpoint for Real-time Status ---

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time agent status updates.
    
    Connect to receive status updates during plan generation.
    Send JSON messages to trigger generation.
    """
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            action = data.get("action")
            
            if action == "analyze":
                # Run analysis with status updates
                async def status_callback(status: AgentStatusUpdate):
                    await manager.send_status(client_id, status)
                
                result = await analyze_request(
                    topic=data.get("topic", ""),
                    chat_history=data.get("chatHistory", []),
                    status_callback=status_callback
                )
                
                await websocket.send_json({
                    "type": "analysis_complete",
                    "data": result
                })
            
            elif action == "generate":
                # Run full generation with status updates
                async def status_callback(status: AgentStatusUpdate):
                    await manager.send_status(client_id, status)
                
                try:
                    from .models import UploadedFile
                    file = None
                    if data.get("file"):
                        file = UploadedFile(**data["file"])
                    
                    project = await generate_project_plan(
                        topic=data.get("topic", ""),
                        context=data.get("context", ""),
                        file=file,
                        status_callback=status_callback
                    )
                    
                    await websocket.send_json({
                        "type": "generation_complete",
                        "data": project.model_dump(by_alias=True)
                    })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
            
            elif action == "chat":
                # Run chat with status updates
                async def status_callback(status: AgentStatusUpdate):
                    await manager.send_status(client_id, status)
                
                try:
                    project = ProjectData(**data.get("project", {}))
                    
                    result = await chat_with_manager(
                        project=project,
                        message=data.get("message", ""),
                        history=data.get("history", []),
                        status_callback=status_callback
                    )
                    
                    await websocket.send_json({
                        "type": "chat_complete",
                        "data": result
                    })
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
            
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        manager.disconnect(client_id)
        print(f"WebSocket error: {e}")
