"""
Orchestrator - Coordinates the multi-agent workflow for project plan generation.
Implements the agent pipeline with validation loops.
"""

import json
import logging
import os
from typing import AsyncGenerator, Callable, Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..models import (
    Task, Subtask, ProjectData, AgentStatusUpdate, AgentType,
    ComplexityLevel, UploadedFile
)
from ..config import get_settings

# Ensure GOOGLE_API_KEY is set in environment for ADK
settings = get_settings()
if settings.google_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
else:
    raise ValueError("GOOGLE_API_KEY not set in .env file")
from .analyst import analyst_agent, file_validator_agent
from .architect import create_architect_agent
from .estimator import create_estimator_agent
from .reviewer import structure_reviewer, estimate_reviewer, final_reviewer
from .manager import create_manager_agent
from .scheduler import recalculate_schedule, calculate_total_duration


# Setup logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# Session service for ADK runners
session_service = InMemorySessionService()


async def run_agent_with_status(
    agent,
    user_message: str,
    status_callback: Callable[[AgentStatusUpdate], Any] | None = None,
    agent_type: AgentType = AgentType.ANALYST,
    status_message: str = "Processing..."
) -> dict:
    """
    Run an ADK agent and optionally send status updates.
    
    Args:
        agent: The LlmAgent to run
        user_message: The user's input message
        status_callback: Optional callback for status updates
        agent_type: Type of agent for status reporting
        status_message: Message to show during processing
        
    Returns:
        Parsed JSON response from the agent
    """
    logger.info(f"Running agent: {agent.name} with message length: {len(user_message)}")
    
    if status_callback:
        await status_callback(AgentStatusUpdate(
            active=True,
            agent=agent_type,
            message=status_message
        ))
    
    try:
        # Create a runner for this agent
        runner = Runner(
            agent=agent,
            app_name="kanso_ai",
            session_service=session_service
        )
        
        # Create a session and run
        session = await session_service.create_session(
            app_name="kanso_ai",
            user_id="kanso_user"
        )
        
        logger.info(f"Session created: {session.id}")
        
        result_text = ""
        
        # Create proper Content object for the message
        user_content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        )
        
        async for event in runner.run_async(
            user_id="kanso_user",
            session_id=session.id,
            new_message=user_content
        ):
            # Log event type for debugging
            event_type = type(event).__name__
            logger.debug(f"Received event: {event_type}")
            
            # Collect text from agent responses
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            result_text = part.text
                            logger.info(f"Got response text length: {len(result_text)}")
        
        # Parse JSON response
        try:
            parsed = json.loads(result_text) if result_text else {}
            logger.info(f"Agent {agent.name} completed successfully")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from {agent.name}: {e}")
            logger.error(f"Raw response: {result_text[:500]}...")
            return {"error": "Failed to parse agent response", "raw": result_text}
            
    except Exception as e:
        logger.error(f"Agent {agent.name} failed with error: {e}")
        raise


def parse_tasks_from_plan(plan_data: dict) -> list[Task]:
    """Convert raw plan data to Task models."""
    tasks = []
    for t in plan_data.get("tasks", []):
        subtasks = [
            Subtask(
                name=st.get("name", ""),
                description=st.get("description"),
                duration=float(st.get("duration", 0.5))
            )
            for st in t.get("subtasks", [])
        ]
        
        complexity_str = t.get("complexity", "Medium")
        try:
            complexity = ComplexityLevel(complexity_str)
        except ValueError:
            complexity = ComplexityLevel.MEDIUM
        
        task = Task(
            id=t.get("id", ""),
            name=t.get("name", ""),
            phase=t.get("phase", ""),
            startOffset=float(t.get("startOffset", 0)),
            duration=max(float(t.get("duration", 1)), 0.5),
            buffer=float(t.get("buffer", 0)),
            dependencies=t.get("dependencies", []),
            description=t.get("description"),
            complexity=complexity,
            subtasks=subtasks
        )
        tasks.append(task)
    
    return tasks


async def analyze_request(
    topic: str,
    chat_history: list[str] = None,
    status_callback: Callable[[AgentStatusUpdate], Any] | None = None
) -> dict:
    """
    Run the Analyst Agent to analyze a project request.
    
    Returns:
        Dict with needsClarification, questions, and reasoning
    """
    history_context = json.dumps(chat_history or [])
    prompt = f"""User Topic: "{topic}"
Previous Context: {history_context}

Analyze this project request and determine if clarification is needed."""

    return await run_agent_with_status(
        agent=analyst_agent,
        user_message=prompt,
        status_callback=status_callback,
        agent_type=AgentType.ANALYST,
        status_message="Analyzing project scope and identifying gaps..."
    )


async def check_file_relevance(
    topic: str,
    file: UploadedFile,
    status_callback: Callable[[AgentStatusUpdate], Any] | None = None
) -> dict:
    """
    Check if an uploaded file is relevant to the project topic.
    
    Returns:
        Dict with isRelevant and reason
    """
    prompt = f"""User Topic: "{topic}"
Attached File: "{file.name}"

Determine if this file is relevant to the project topic."""

    return await run_agent_with_status(
        agent=file_validator_agent,
        user_message=prompt,
        status_callback=status_callback,
        agent_type=AgentType.ANALYST,
        status_message=f"Checking file relevance to project topic..."
    )


async def generate_project_plan(
    topic: str,
    context: str,
    file: UploadedFile | None = None,
    status_callback: Callable[[AgentStatusUpdate], Any] | None = None
) -> ProjectData:
    """
    Main orchestration function to generate a complete project plan.
    Runs the full agent pipeline: Architect -> Reviewer -> Estimator -> Reviewer -> Final
    
    Args:
        topic: The project topic/goal
        context: Additional context (clarification answers, etc.)
        file: Optional uploaded file
        status_callback: Callback for status updates
        
    Returns:
        Complete ProjectData with scheduled tasks
    """
    augmented_context = context
    file_to_use = file
    
    # Step 0: Check file relevance if provided
    if file:
        relevance = await check_file_relevance(topic, file, status_callback)
        if not relevance.get("isRelevant", True):
            file_to_use = None
            augmented_context += f"\n[System Note: User uploaded file '{file.name}' but it was deemed irrelevant. Reason: {relevance.get('reason', 'Unknown')}]"
    
    # Step 1: Architect creates structure
    architect = create_architect_agent()
    file_note = f"\n**User uploaded file: {file_to_use.name}. Use this as primary context.**" if file_to_use else ""
    
    architect_prompt = f"""Create a project plan for: "{topic}"
User Context: "{augmented_context}"
{file_note}"""

    structural_plan = await run_agent_with_status(
        agent=architect,
        user_message=architect_prompt,
        status_callback=status_callback,
        agent_type=AgentType.ARCHITECT,
        status_message="Designing project structure (Phases, Tasks, Dependencies)..."
    )
    
    # Step 1.5: Validate structure
    structure_check = await run_agent_with_status(
        agent=structure_reviewer,
        user_message=f"Review this project structure:\n{json.dumps(structural_plan)}",
        status_callback=status_callback,
        agent_type=AgentType.REVIEWER,
        status_message="Validating logical dependencies and structural completeness..."
    )
    
    # Retry if invalid
    if not structure_check.get("isValid", True):
        critique = structure_check.get("critique", "Please improve the structure.")
        architect_with_feedback = create_architect_agent(critique)
        
        structural_plan = await run_agent_with_status(
            agent=architect_with_feedback,
            user_message=architect_prompt,
            status_callback=status_callback,
            agent_type=AgentType.ARCHITECT,
            status_message=f"Re-designing structure based on feedback..."
        )
    
    # Step 2: Estimator calculates times
    estimator = create_estimator_agent()
    
    estimated_plan = await run_agent_with_status(
        agent=estimator,
        user_message=f"Estimate times for this project structure:\n{json.dumps(structural_plan)}",
        status_callback=status_callback,
        agent_type=AgentType.ESTIMATOR,
        status_message="Calculating bottom-up estimates for every subtask..."
    )
    
    # Step 2.5: Validate estimates
    estimate_check = await run_agent_with_status(
        agent=estimate_reviewer,
        user_message=f"Review these time estimates:\n{json.dumps(estimated_plan)}",
        status_callback=status_callback,
        agent_type=AgentType.REVIEWER,
        status_message="Sanity checking time estimates and buffer allocations..."
    )
    
    # Retry if invalid
    if not estimate_check.get("isValid", True):
        critique = estimate_check.get("critique", "Please improve the estimates.")
        estimator_with_feedback = create_estimator_agent(critique)
        
        estimated_plan = await run_agent_with_status(
            agent=estimator_with_feedback,
            user_message=f"Estimate times for this project structure:\n{json.dumps(structural_plan)}",
            status_callback=status_callback,
            agent_type=AgentType.ESTIMATOR,
            status_message="Recalculating estimates based on feedback..."
        )
    
    # Step 3: Final cleanup
    refined_plan = await run_agent_with_status(
        agent=final_reviewer,
        user_message=f"Clean up and finalize this plan:\n{json.dumps(estimated_plan)}",
        status_callback=status_callback,
        agent_type=AgentType.REVIEWER,
        status_message="Finalizing schedule and formatting output..."
    )
    
    # Step 4: Parse and schedule tasks
    tasks = parse_tasks_from_plan(refined_plan)
    scheduled_tasks = recalculate_schedule(tasks)
    total_duration = calculate_total_duration(scheduled_tasks)
    
    # Build final ProjectData
    project = ProjectData(
        title=refined_plan.get("projectTitle", topic),
        description=refined_plan.get("projectSummary", ""),
        assumptions=refined_plan.get("assumptions", []),
        tasks=scheduled_tasks,
        totalDuration=total_duration
    )
    
    # Clear status
    if status_callback:
        await status_callback(AgentStatusUpdate(
            active=False,
            agent=AgentType.MANAGER,
            message=""
        ))
    
    return project


def merge_task_updates(existing_tasks: list[Task], updated_plan: dict) -> list[Task]:
    """
    Merge partial task updates from the Manager with existing tasks.
    
    This ensures that even if the LLM returns partial task data, we preserve
    all fields from the original tasks.
    
    Strategy:
    - Create a lookup of existing tasks by ID
    - For each task in updated_plan:
      - If ID exists: merge updated fields into existing task
      - If ID is new: add the new task
    - Preserve tasks that weren't modified
    """
    # Create lookup by ID
    existing_by_id = {t.id: t for t in existing_tasks}
    updated_tasks_data = updated_plan.get("tasks", [])
    
    # Track which IDs we've seen in the update
    seen_ids = set()
    result_tasks = []
    
    for ut in updated_tasks_data:
        task_id = ut.get("id", "")
        seen_ids.add(task_id)
        
        if task_id in existing_by_id:
            # Merge: use existing values as defaults, override with new values
            existing = existing_by_id[task_id]
            
            # Parse subtasks
            subtasks = []
            if ut.get("subtasks"):
                for st in ut["subtasks"]:
                    subtasks.append(Subtask(
                        name=st.get("name", ""),
                        description=st.get("description"),
                        duration=float(st.get("duration") or 0.5)
                    ))
            else:
                subtasks = existing.subtasks
            
            # Determine complexity
            complexity_str = ut.get("complexity", existing.complexity.value)
            try:
                complexity = ComplexityLevel(complexity_str)
            except ValueError:
                complexity = existing.complexity
            
            # Merge task - use new value if provided and valid, else keep existing
            merged_task = Task(
                id=task_id,
                name=ut.get("name") or existing.name,
                phase=ut.get("phase") or existing.phase,
                startOffset=0,  # Will be recalculated by scheduler
                duration=float(ut.get("duration")) if ut.get("duration") is not None and ut.get("duration") > 0 else existing.duration,
                buffer=float(ut.get("buffer")) if ut.get("buffer") is not None else existing.buffer,
                dependencies=ut.get("dependencies") if ut.get("dependencies") is not None else existing.dependencies,
                description=ut.get("description") if ut.get("description") is not None else existing.description,
                complexity=complexity,
                subtasks=subtasks
            )
            result_tasks.append(merged_task)
        else:
            # New task - parse it fresh
            subtasks = [
                Subtask(
                    name=st.get("name", ""),
                    description=st.get("description"),
                    duration=float(st.get("duration") or 0.5)
                )
                for st in ut.get("subtasks", [])
            ]
            
            complexity_str = ut.get("complexity", "Medium")
            try:
                complexity = ComplexityLevel(complexity_str)
            except ValueError:
                complexity = ComplexityLevel.MEDIUM
            
            new_task = Task(
                id=task_id or f"new_task_{len(result_tasks)}",
                name=ut.get("name", "New Task"),
                phase=ut.get("phase", "New Phase"),
                startOffset=0,
                duration=max(float(ut.get("duration") or 1), 0.5),
                buffer=float(ut.get("buffer") or 0),
                dependencies=ut.get("dependencies", []),
                description=ut.get("description"),
                complexity=complexity,
                subtasks=subtasks
            )
            result_tasks.append(new_task)
    
    # Preserve any existing tasks that weren't mentioned in the update
    # (unless the Manager explicitly wanted them removed - which would be indicated by a smaller task list)
    # If the update has very few tasks (< 50% of original), it's likely a partial update
    if len(updated_tasks_data) < len(existing_tasks) * 0.5:
        logger.warning(f"Manager returned only {len(updated_tasks_data)} tasks, original had {len(existing_tasks)}. Merging with originals.")
        for task_id, existing_task in existing_by_id.items():
            if task_id not in seen_ids:
                result_tasks.append(existing_task)
    
    logger.info(f"Merged tasks: {len(result_tasks)} (from {len(updated_tasks_data)} updates + {len(existing_tasks)} existing)")
    return result_tasks


async def chat_with_manager(
    project: ProjectData,
    message: str,
    history: list[dict],
    status_callback: Callable[[AgentStatusUpdate], Any] | None = None
) -> dict:
    """
    Handle a chat message with the Project Manager agent.
    
    Args:
        project: Current project data
        message: User's chat message
        history: Previous conversation history
        status_callback: Callback for status updates
        
    Returns:
        Dict with 'reply' and optional 'updatedPlan'
    """
    # Convert project to JSON for agent context
    project_json = project.model_dump_json()
    
    # Create manager with current project context
    manager = create_manager_agent(project_json)
    
    # Format history
    history_text = "\n".join([
        f"{h.get('role', 'user')}: {h.get('content', '')}"
        for h in history[-10:]  # Last 10 messages for context
    ])
    
    prompt = f"""Previous conversation:
{history_text}

User: {message}

Respond to this message. If the user wants to modify the plan, return an updatedPlan."""

    response = await run_agent_with_status(
        agent=manager,
        user_message=prompt,
        status_callback=status_callback,
        agent_type=AgentType.MANAGER,
        status_message="Processing your request and refining the project structure..."
    )
    
    # If there's an updated plan, process it
    if response.get("updatedPlan"):
        updated_tasks_count = len(response["updatedPlan"].get("tasks", []))
        logger.info(f"Manager returned updatedPlan with {updated_tasks_count} tasks (original: {len(project.tasks)})")
        
        # Log task details for debugging
        for t in response["updatedPlan"].get("tasks", [])[:2]:
            logger.info(f"Task sample: id={t.get('id')}, duration={t.get('duration')}, buffer={t.get('buffer')}")
        
        # Use merge strategy to preserve existing task data
        merged_tasks = merge_task_updates(project.tasks, response["updatedPlan"])
        scheduled_tasks = recalculate_schedule(merged_tasks)
        total_duration = calculate_total_duration(scheduled_tasks)
        
        logger.info(f"Final schedule: {len(scheduled_tasks)} tasks, total duration: {total_duration}")
        
        response["updatedPlan"] = {
            "projectTitle": response["updatedPlan"].get("projectTitle") or project.title,
            "projectSummary": response["updatedPlan"].get("projectSummary") or project.description,
            "assumptions": response["updatedPlan"].get("assumptions") or project.assumptions,
            "tasks": [t.model_dump(by_alias=True) for t in scheduled_tasks],
            "totalDuration": total_duration
        }
    
    return response
