"""
Pydantic models for API requests and responses.
Mirrors the TypeScript types for frontend compatibility.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class ComplexityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class AgentType(str, Enum):
    ANALYST = "Analyst"
    ARCHITECT = "Architect"
    ESTIMATOR = "Estimator"
    REVIEWER = "Reviewer"
    MANAGER = "Manager"


class Subtask(BaseModel):
    name: str
    description: Optional[str] = None
    duration: float = Field(description="Duration in hours")


class Task(BaseModel):
    id: str
    name: str
    phase: str
    start_offset: float = Field(alias="startOffset", description="Hours from project start")
    duration: float = Field(description="Estimated hours")
    buffer: float = Field(description="Buffer hours")
    dependencies: list[str] = Field(default_factory=list)
    description: Optional[str] = None
    complexity: ComplexityLevel = ComplexityLevel.MEDIUM
    subtasks: list[Subtask] = Field(default_factory=list)

    class Config:
        populate_by_name = True


class ProjectData(BaseModel):
    title: str
    description: str
    assumptions: list[str] = Field(default_factory=list)
    tasks: list[Task] = Field(default_factory=list)
    total_duration: float = Field(alias="totalDuration", default=0)

    class Config:
        populate_by_name = True


class UploadedFile(BaseModel):
    name: str
    type: str
    data: str  # Base64 encoded


# --- Request Models ---

class AnalyzeRequest(BaseModel):
    topic: str
    chat_history: list[str] = Field(default_factory=list, alias="chatHistory")

    class Config:
        populate_by_name = True


class GeneratePlanRequest(BaseModel):
    topic: str
    context: str
    file: Optional[UploadedFile] = None


class ClarificationRequest(BaseModel):
    topic: str
    answers: dict[str, str]


class ChatMessage(BaseModel):
    role: str  # "user" or "model"
    content: str


class ChatRequest(BaseModel):
    project: ProjectData
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


# --- Response Models ---

class AnalysisResponse(BaseModel):
    needs_clarification: bool = Field(alias="needsClarification")
    questions: list[str] = Field(default_factory=list)
    reasoning: str = ""

    class Config:
        populate_by_name = True


class ValidationResponse(BaseModel):
    is_valid: bool = Field(alias="isValid")
    critique: str = ""

    class Config:
        populate_by_name = True


class FileRelevanceResponse(BaseModel):
    is_relevant: bool = Field(alias="isRelevant")
    reason: str = ""

    class Config:
        populate_by_name = True


class ChatResponse(BaseModel):
    reply: str
    updated_plan: Optional[ProjectData] = Field(alias="updatedPlan", default=None)

    class Config:
        populate_by_name = True


class AgentStatusUpdate(BaseModel):
    """Sent via WebSocket to update agent status in real-time"""
    active: bool
    agent: AgentType
    message: str


class PlanGenerationResult(BaseModel):
    project: ProjectData
    success: bool
    error: Optional[str] = None


class CalendarExportRequest(BaseModel):
    """Request to export project as calendar file"""
    project: ProjectData
    start_date: Optional[str] = Field(
        default=None, 
        alias="startDate",
        description="ISO format date string (YYYY-MM-DD) for when to start the project"
    )
    hours_per_day: float = Field(
        default=8.0, 
        alias="hoursPerDay",
        description="Working hours per day"
    )
    include_weekends: bool = Field(
        default=False, 
        alias="includeWeekends",
        description="Whether to include weekends as working days"
    )

    class Config:
        populate_by_name = True
