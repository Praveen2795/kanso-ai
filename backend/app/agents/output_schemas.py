"""
Pydantic output schemas for ADK agents.
These replace the google.genai.types.Schema definitions.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ClarificationOutput(BaseModel):
    """Output schema for the Analyst agent's clarification check."""
    needsClarification: bool = Field(description="Whether clarification is needed from the user")
    questions: list[str] = Field(default_factory=list, description="List of clarifying questions")
    reasoning: str = Field(default="", description="Reasoning behind the decision")


class FileRelevanceOutput(BaseModel):
    """Output schema for file relevance validation."""
    isRelevant: bool = Field(description="Whether the file is relevant to the topic")
    reason: str = Field(default="", description="Explanation for the relevance decision")


class ValidationOutput(BaseModel):
    """Output schema for reviewer validation."""
    isValid: bool = Field(description="Whether the input passes validation")
    critique: str = Field(default="", description="Detailed critique if invalid")


class SubtaskOutput(BaseModel):
    """Schema for a subtask within a task."""
    name: str
    description: Optional[str] = None
    duration: float = Field(description="Duration in hours")


class TaskOutput(BaseModel):
    """Schema for a task in the project plan."""
    id: str
    name: str
    phase: str
    description: Optional[str] = None
    complexity: str = Field(default="Medium", description="Low, Medium, or High")
    subtasks: list[SubtaskOutput] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list, description="IDs of dependent tasks")
    duration: float = Field(default=0, description="Total estimated hours")
    buffer: float = Field(default=0, description="Buffer hours")
    startOffset: float = Field(default=0, description="Hours from project start")


class ProjectPlanOutput(BaseModel):
    """Output schema for the full project plan."""
    projectTitle: str
    projectSummary: Optional[str] = None
    assumptions: list[str] = Field(default_factory=list, description="Assumptions made during planning")
    tasks: list[TaskOutput] = Field(default_factory=list)


class ChatOutput(BaseModel):
    """Output schema for chat responses."""
    reply: str = Field(description="The response message to the user")
    updatedPlan: Optional[ProjectPlanOutput] = Field(default=None, description="Updated plan if changes were made")
