"""
FastAPI application with REST API endpoints and WebSocket support.
Integrated with Opik for comprehensive AI observability.
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
from .logging_config import setup_logging, get_logger, set_correlation_id
from .middleware import add_logging_middleware, WebSocketLoggingMiddleware
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
from .opik_service import (
    configure_opik,
    log_feedback,
    get_trace_url,
    get_dashboard_url,
    flush_traces,
    is_opik_enabled
)

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    # Startup
    setup_logging()
    
    # Initialize Opik observability
    if settings.opik_enabled:
        opik_configured = configure_opik()
        if opik_configured:
            dashboard_url = get_dashboard_url()
            logger.info(
                f"✅ Opik observability enabled",
                extra={'extra_data': {
                    'opik_workspace': settings.opik_workspace,
                    'opik_project': settings.opik_project_name,
                    'dashboard_url': dashboard_url
                }}
            )
            print(f"\n📊 View traces at: {dashboard_url}\n")
        else:
            logger.warning("Opik observability failed to configure")
    
    logger.info(
        "Kanso.AI Backend starting",
        extra={'extra_data': {
            'host': settings.host,
            'port': settings.port,
            'cors_origins': settings.cors_origins_list,
            'opik_enabled': settings.opik_enabled
        }}
    )
    yield
    # Shutdown
    # Flush any remaining traces to Opik before shutdown
    if settings.opik_enabled:
        flush_traces()
        logger.info("Opik traces flushed on shutdown")
    logger.info("Kanso.AI Backend shutting down")


app = FastAPI(
    title="Kanso.AI API",
    description="AI-powered project planning with multi-agent system",
    version="1.0.0",
    lifespan=lifespan
)

# Add logging middleware (must be added before CORS)
add_logging_middleware(app)

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
        self._logger = get_logger(f"{__name__}.ConnectionManager")
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self._logger.info(
            f"WebSocket connected",
            extra={'extra_data': {'client_id': client_id, 'total_connections': len(self.active_connections)}}
        )
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            self._logger.info(
                f"WebSocket disconnected",
                extra={'extra_data': {'client_id': client_id, 'total_connections': len(self.active_connections)}}
            )
    
    async def send_status(self, client_id: str, status: AgentStatusUpdate):
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(
                    status.model_dump(by_alias=True)
                )
            except Exception as e:
                self._logger.warning(
                    f"Failed to send status to client",
                    extra={'extra_data': {'client_id': client_id, 'error': str(e)}}
                )
                self.disconnect(client_id)


manager = ConnectionManager()


# --- REST API Endpoints ---

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "kanso-ai-backend"}


@app.get("/api/observability/status")
async def observability_status():
    """
    Check Opik observability status.
    Returns configuration state and dashboard URL.
    """
    if not settings.opik_enabled:
        return {
            "enabled": False,
            "message": "Opik not configured. Set OPIK_API_KEY and OPIK_WORKSPACE in .env",
            "dashboard_url": None,
            "setup_instructions": {
                "1": "Sign up at https://www.comet.com/signup",
                "2": "Get your API key from the dashboard",
                "3": "Add OPIK_API_KEY and OPIK_WORKSPACE to backend/.env"
            }
        }
    
    dashboard_url = get_dashboard_url()
    return {
        "enabled": True,
        "workspace": settings.opik_workspace,
        "project": settings.opik_project_name,
        "dashboard_url": dashboard_url,
        "traces_url": f"{dashboard_url}/traces",
        "features": {
            "agent_tracing": "Full multi-agent pipeline tracing",
            "llm_as_judge": "Automatic plan quality evaluation",
            "token_tracking": "Token usage and cost monitoring",
            "user_feedback": "Feedback collection via /api/feedback",
            "callbacks": "Before/after agent callbacks for detailed tracing"
        },
        "metrics": [
            "plan_structure_score",
            "estimate_reasonableness_score",
            "plan_completeness_score",
            "overall_quality"
        ]
    }


class FeedbackRequest(BaseModel):
    """Request model for user feedback on generated plans."""
    trace_id: str
    score: float  # 0.0 to 1.0
    category: str = "user_satisfaction"
    comment: str = ""


@app.post("/api/feedback")
async def submit_feedback(request: FeedbackRequest):
    """
    Submit user feedback on a generated plan.
    
    This logs feedback to Opik for tracking user satisfaction
    and improving the system over time.
    """
    if not settings.opik_enabled:
        return {"status": "skipped", "message": "Opik not configured"}
    
    if not 0.0 <= request.score <= 1.0:
        raise HTTPException(status_code=400, detail="Score must be between 0.0 and 1.0")
    
    log_feedback(
        trace_id=request.trace_id,
        score=request.score,
        category=request.category,
        comment=request.comment
    )
    
    logger.info(
        "User feedback logged",
        extra={'extra_data': {
            'trace_id': request.trace_id,
            'score': request.score,
            'category': request.category
        }}
    )
    
    return {
        "status": "logged",
        "trace_id": request.trace_id,
        "trace_url": get_trace_url(request.trace_id)
    }


@app.post("/api/analyze", response_model=AnalysisResponse)
async def analyze_project_request(request: AnalyzeRequest):
    """
    Analyze a project request and determine if clarification is needed.
    
    This runs the Analyst Agent to:
    - Verify technical terms
    - Check URL accessibility
    - Identify missing context
    """
    logger.info(
        "Starting project analysis",
        extra={'extra_data': {'topic_length': len(request.topic), 'has_history': bool(request.chat_history)}}
    )
    try:
        result = await analyze_request(
            topic=request.topic,
            chat_history=request.chat_history
        )
        
        needs_clarification = result.get("needsClarification", False)
        logger.info(
            "Analysis complete",
            extra={'extra_data': {
                'needs_clarification': needs_clarification,
                'questions_count': len(result.get("questions", []))
            }}
        )
        
        return AnalysisResponse(
            needsClarification=needs_clarification,
            questions=result.get("questions", []),
            reasoning=result.get("reasoning", "")
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
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
    logger.info(
        "Starting plan generation",
        extra={'extra_data': {
            'topic_length': len(request.topic),
            'context_length': len(request.context) if request.context else 0,
            'has_file': request.file is not None
        }}
    )
    try:
        project = await generate_project_plan(
            topic=request.topic,
            context=request.context,
            file=request.file
        )
        
        logger.info(
            "Plan generation complete",
            extra={'extra_data': {
                'project_title': project.title,
                'task_count': len(project.tasks),
                'total_duration': project.totalDuration
            }}
        )
        
        return PlanGenerationResult(
            project=project,
            success=True
        )
    except Exception as e:
        logger.error(f"Plan generation failed: {e}", exc_info=True)
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
    logger.info(
        "Processing chat message",
        extra={'extra_data': {
            'message_length': len(request.message),
            'history_length': len(request.history),
            'project_title': request.project.title
        }}
    )
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
            logger.info(
                "Chat resulted in plan update",
                extra={'extra_data': {'new_task_count': len(tasks)}}
            )
        
        logger.info("Chat message processed successfully")
        
        return ChatResponse(
            reply=result.get("reply", "I couldn't process that request."),
            updatedPlan=updated_plan
        )
    except Exception as e:
        logger.error(f"Chat processing failed: {e}", exc_info=True)
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
    logger.info(
        "Starting calendar export",
        extra={'extra_data': {
            'project_title': request.project.title,
            'task_count': len(request.project.tasks),
            'hours_per_day': request.hours_per_day,
            'include_weekends': request.include_weekends
        }}
    )
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
        
        logger.info(
            "Calendar export complete",
            extra={'extra_data': {'filename': filename, 'content_length': len(ics_content)}}
        )
        
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
        logger.error(f"Calendar export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# --- WebSocket Endpoint for Real-time Status ---

@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for real-time agent status updates.
    
    Connect to receive status updates during plan generation.
    Send JSON messages to trigger generation.
    """
    # Set correlation ID for this WebSocket session
    set_correlation_id(f"ws-{client_id[:8]}")
    
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            
            action = data.get("action")
            logger.debug(f"WebSocket action received", extra={'extra_data': {'action': action, 'client_id': client_id}})
            
            if action == "analyze":
                # Run analysis with status updates
                logger.info("Starting WebSocket analysis", extra={'extra_data': {'client_id': client_id}})
                
                async def status_callback(status: AgentStatusUpdate):
                    await manager.send_status(client_id, status)
                
                result = await analyze_request(
                    topic=data.get("topic", ""),
                    chat_history=data.get("chatHistory", []),
                    status_callback=status_callback
                )
                
                logger.info("WebSocket analysis complete", extra={'extra_data': {'client_id': client_id}})
                
                await websocket.send_json({
                    "type": "analysis_complete",
                    "data": result
                })
            
            elif action == "generate":
                # Run full generation with status updates
                logger.info("Starting WebSocket generation", extra={'extra_data': {'client_id': client_id}})
                
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
                    
                    logger.info(
                        "WebSocket generation complete",
                        extra={'extra_data': {
                            'client_id': client_id,
                            'project_title': project.title,
                            'task_count': len(project.tasks)
                        }}
                    )
                    
                    await websocket.send_json({
                        "type": "generation_complete",
                        "data": project.model_dump(by_alias=True)
                    })
                except Exception as e:
                    logger.error(f"WebSocket generation failed: {e}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "message": str(e)
                    })
            
            elif action == "chat":
                # Run chat with status updates
                logger.info("Starting WebSocket chat", extra={'extra_data': {'client_id': client_id}})
                
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
                    
                    logger.info("WebSocket chat complete", extra={'extra_data': {'client_id': client_id}})
                    
                    await websocket.send_json({
                        "type": "chat_complete",
                        "data": result
                    })
                except Exception as e:
                    logger.error(f"WebSocket chat failed: {e}", exc_info=True)
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
        logger.error(f"WebSocket error: {e}", exc_info=True)
