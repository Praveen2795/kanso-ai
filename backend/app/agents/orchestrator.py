"""
Orchestrator - Coordinates the multi-agent workflow for project plan generation.
Implements the agent pipeline with validation loops.
Integrated with Opik for comprehensive observability and evaluation.
"""

import json
import os
import time
from typing import AsyncGenerator, Callable, Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from ..models import (
    Task, Subtask, ProjectData, AgentStatusUpdate, AgentType,
    ComplexityLevel, UploadedFile
)
from ..config import get_settings
from ..logging_config import get_logger, log_execution_time

# Import Opik observability
from ..opik_service import (
    create_adk_tracer,
    instrument_agent,
    evaluate_plan_quality,
    track_agent_performance,
    track_agent_run,
    flush_traces,
    configure_opik,
    is_opik_enabled,
    get_dashboard_url,
)

# Try to import Opik for tracing decorators
try:
    from opik import track, opik_context
    OPIK_AVAILABLE = True
except ImportError:
    OPIK_AVAILABLE = False
    def track(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args or callable(args[0]) else decorator

# Ensure GOOGLE_API_KEY is set in environment for ADK
settings = get_settings()
if settings.google_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key
else:
    raise ValueError("GOOGLE_API_KEY not set in .env file")
from .analyst import analyst_agent, file_validator_agent
from .architect import create_architect_agent
from .estimator import create_estimator_agent
from .reviewer import (
    structure_reviewer, estimate_reviewer, final_reviewer,
    MAX_VALIDATION_ITERATIONS
)
from .manager import create_manager_agent
from .scheduler import recalculate_schedule, calculate_total_duration
from .research import research_urls, extract_urls, auto_research_context


# Setup logging using centralized config
logger = get_logger(__name__)

# Session service for ADK runners
session_service = InMemorySessionService()

# Initialize Opik on module load
if settings.opik_enabled:
    configure_opik()
    logger.info("Opik observability initialized for orchestrator")


async def run_agent_with_status(
    agent,
    user_message: str,
    status_callback: Callable[[AgentStatusUpdate], Any] | None = None,
    agent_type: AgentType = AgentType.ANALYST,
    status_message: str = "Processing...",
    trace_metadata: dict | None = None
) -> dict:
    """
    Run an ADK agent and optionally send status updates.
    Integrated with Opik for tracing and performance monitoring.
    
    Args:
        agent: The LlmAgent to run
        user_message: The user's input message
        status_callback: Optional callback for status updates
        agent_type: Type of agent for status reporting
        status_message: Message to show during processing
        trace_metadata: Optional metadata to add to Opik trace
        
    Returns:
        Parsed JSON response from the agent
    """
    start_time = time.time()
    agent_name = getattr(agent, 'name', 'unknown')
    
    logger.info(
        f"Running agent: {agent_name}",
        extra={'extra_data': {'agent': agent_name, 'message_length': len(user_message)}}
    )
    
    if status_callback:
        await status_callback(AgentStatusUpdate(
            active=True,
            agent=agent_type,
            message=status_message
        ))
    
    try:
        # Instrument agent with Opik tracer if available
        if settings.opik_enabled and OPIK_AVAILABLE:
            tracer = create_adk_tracer(
                name=f"kanso-{agent_name}",
                tags=[agent_type.value, "orchestrator"],
                metadata={
                    "agent_type": agent_type.value,
                    "status_message": status_message,
                    **(trace_metadata or {})
                }
            )
            instrumented_agent = instrument_agent(agent, tracer)
        else:
            instrumented_agent = agent
        
        # Create a runner for this agent
        runner = Runner(
            agent=instrumented_agent,
            app_name="kanso_ai",
            session_service=session_service
        )
        
        # Create a session and run
        session = await session_service.create_session(
            app_name="kanso_ai",
            user_id="kanso_user"
        )
        
        logger.debug(f"Session created", extra={'extra_data': {'session_id': session.id}})
        
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
            logger.debug(f"Received event", extra={'extra_data': {'event_type': event_type}})
            
            # Collect text from agent responses
            if hasattr(event, 'content') and event.content:
                if hasattr(event.content, 'parts'):
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            result_text = part.text
                            logger.debug(f"Got response", extra={'extra_data': {'response_length': len(result_text)}})
        
        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Parse JSON response
        try:
            parsed = json.loads(result_text) if result_text else {}
            logger.info(
                f"Agent completed successfully",
                extra={'extra_data': {'agent': agent.name, 'response_keys': list(parsed.keys()) if isinstance(parsed, dict) else 'non-dict'}}
            )
            return parsed
        except json.JSONDecodeError as e:
            logger.error(
                f"Failed to parse JSON from agent",
                extra={'extra_data': {'agent': agent.name, 'error': str(e), 'raw_preview': result_text[:200]}}
            )
            return {"error": "Failed to parse agent response", "raw": result_text}
            
    except Exception as e:
        logger.error(
            f"Agent failed",
            extra={'extra_data': {'agent': agent.name, 'error': str(e)}},
            exc_info=True
        )
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


@track(
    name="analyze_project_request",
    tags=["analyst", "clarification"],
    capture_input=True,
    capture_output=True
)
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
        status_message="Analyzing project scope and identifying gaps...",
        trace_metadata={"topic_length": len(topic)}
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


@track(
    name="generate_project_plan",
    tags=["orchestrator", "plan-generation", "multi-agent"],
    capture_input=True,
    capture_output=True
)
async def generate_project_plan(
    topic: str,
    context: str,
    file: UploadedFile | None = None,
    status_callback: Callable[[AgentStatusUpdate], Any] | None = None
) -> ProjectData:
    """
    Main orchestration function to generate a complete project plan.
    Runs the full agent pipeline: Research -> Architect -> Reviewer -> Estimator -> Reviewer -> Final
    Fully traced with Opik for observability and LLM-as-judge evaluation.
    
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
    
    # Step 0a: Research URLs if any are found in topic or context
    combined_text = f"{topic} {context}"
    urls_found = extract_urls(combined_text)
    
    if urls_found:
        if status_callback:
            await status_callback(AgentStatusUpdate(
                active=True,
                agent=AgentType.RESEARCHER,
                message=f"Researching {len(urls_found)} URL(s) using Google Search..."
            ))
        
        research_result = await research_urls(combined_text)
        
        if research_result.get('success') and research_result.get('context_summary'):
            augmented_context += f"\n\n{research_result['context_summary']}"
            logger.info(
                "Google Search research complete",
                extra={'extra_data': {
                    'urls_provided': len(research_result['urls_found']),
                    'sources_found': len(research_result.get('sources', []))
                }}
            )
            
            # Report success with sources count
            if status_callback:
                source_count = len(research_result.get('sources', []))
                await status_callback(AgentStatusUpdate(
                    active=True,
                    agent=AgentType.RESEARCHER,
                    message=f"✓ URL research complete - found {source_count} relevant sources"
                ))
        
        # Report any research errors
        if not research_result.get('success') and status_callback:
            error_msg = research_result.get('error', 'Unknown error')
            await status_callback(AgentStatusUpdate(
                active=True,
                agent=AgentType.RESEARCHER,
                message=f"⚠️ Research encountered an issue: {error_msg[:100]}"
            ))
    
    # Step 0a.2: Auto-research unfamiliar terms from clarification answers
    if context and len(context) > 20:
        if status_callback:
            await status_callback(AgentStatusUpdate(
                active=True,
                agent=AgentType.RESEARCHER,
                message="Analyzing context for unfamiliar terms..."
            ))
        
        auto_research_result = await auto_research_context(topic, context)
        
        if auto_research_result.get('terms_found'):
            terms = auto_research_result['terms_found']
            if status_callback:
                await status_callback(AgentStatusUpdate(
                    active=True,
                    agent=AgentType.RESEARCHER,
                    message=f"Researching terms: {', '.join(terms)}..."
                ))
            
            if auto_research_result.get('success') and auto_research_result.get('context_summary'):
                augmented_context += f"\n\n{auto_research_result['context_summary']}"
                logger.info(
                    "Auto-research of terms complete",
                    extra={'extra_data': {
                        'terms_researched': terms,
                        'sources_found': len(auto_research_result.get('sources', []))
                    }}
                )
                
                if status_callback:
                    source_count = len(auto_research_result.get('sources', []))
                    await status_callback(AgentStatusUpdate(
                        active=True,
                        agent=AgentType.RESEARCHER,
                        message=f"✓ Term research complete - researched {len(terms)} term(s), found {source_count} sources"
                    ))
            
            if not auto_research_result.get('success') and status_callback:
                await status_callback(AgentStatusUpdate(
                    active=True,
                    agent=AgentType.RESEARCHER,
                    message="⚠️ Term research encountered an issue, continuing without"
                ))
    
    # Step 0b: Check file relevance if provided
    if file:
        relevance = await check_file_relevance(topic, file, status_callback)
        if not relevance.get("isRelevant", True):
            file_to_use = None
            augmented_context += f"\n[System Note: User uploaded file '{file.name}' but it was deemed irrelevant. Reason: {relevance.get('reason', 'Unknown')}]"
    
    # Step 1: Architecture Loop (Architect + Structure Reviewer) with max iterations
    file_note = f"\n**User uploaded file: {file_to_use.name}. Use this as primary context.**" if file_to_use else ""
    
    architect_prompt = f"""Create a project plan for: "{topic}"
User Context: "{augmented_context}"
{file_note}"""

    structural_plan = None
    structure_valid = False
    critique = None
    
    for iteration in range(1, MAX_VALIDATION_ITERATIONS + 1):
        logger.info(f"Architecture iteration {iteration}/{MAX_VALIDATION_ITERATIONS}")
        
        # Create architect (with critique if this is a retry)
        architect = create_architect_agent(critique)
        
        # Run architect
        structural_plan = await run_agent_with_status(
            agent=architect,
            user_message=architect_prompt,
            status_callback=status_callback,
            agent_type=AgentType.ARCHITECT,
            status_message=f"Designing project structure (iteration {iteration}/{MAX_VALIDATION_ITERATIONS})...",
            trace_metadata={"iteration": iteration, "has_critique": critique is not None}
        )
        
        # Validate structure
        structure_check = await run_agent_with_status(
            agent=structure_reviewer,
            user_message=f"Review this project structure:\n{json.dumps(structural_plan)}",
            status_callback=status_callback,
            agent_type=AgentType.REVIEWER,
            status_message=f"Validating structure (iteration {iteration}/{MAX_VALIDATION_ITERATIONS})...",
            trace_metadata={"iteration": iteration}
        )
        
        structure_valid = structure_check.get("isValid", True)
        
        if structure_valid:
            logger.info(f"Structure validated on iteration {iteration}")
            break
        else:
            critique = structure_check.get("critique", "Please improve the structure.")
            logger.info(f"Structure rejected on iteration {iteration}, critique: {critique[:100]}...")
            
            if iteration < MAX_VALIDATION_ITERATIONS:
                if status_callback:
                    await status_callback(AgentStatusUpdate(
                        active=True,
                        agent=AgentType.ARCHITECT,
                        message=f"Structure needs improvement, retrying ({iteration}/{MAX_VALIDATION_ITERATIONS})..."
                    ))
    
    if not structure_valid:
        logger.warning(f"Structure validation exhausted max iterations ({MAX_VALIDATION_ITERATIONS}), proceeding anyway")
    
    # Step 2: Estimation Loop (Estimator + Estimate Reviewer) with max iterations
    estimated_plan = None
    estimate_valid = False
    estimate_critique = None
    
    for iteration in range(1, MAX_VALIDATION_ITERATIONS + 1):
        logger.info(f"Estimation iteration {iteration}/{MAX_VALIDATION_ITERATIONS}")
        
        # Create estimator (with critique if this is a retry)
        estimator = create_estimator_agent(estimate_critique)
        
        # Run estimator
        estimated_plan = await run_agent_with_status(
            agent=estimator,
            user_message=f"Estimate times for this project structure:\n{json.dumps(structural_plan)}",
            status_callback=status_callback,
            agent_type=AgentType.ESTIMATOR,
            status_message=f"Calculating time estimates (iteration {iteration}/{MAX_VALIDATION_ITERATIONS})...",
            trace_metadata={"iteration": iteration, "has_critique": estimate_critique is not None}
        )
        
        # Validate estimates
        estimate_check = await run_agent_with_status(
            agent=estimate_reviewer,
            user_message=f"Review these time estimates:\n{json.dumps(estimated_plan)}",
            status_callback=status_callback,
            agent_type=AgentType.REVIEWER,
            status_message=f"Validating estimates (iteration {iteration}/{MAX_VALIDATION_ITERATIONS})...",
            trace_metadata={"iteration": iteration}
        )
        
        estimate_valid = estimate_check.get("isValid", True)
        
        if estimate_valid:
            logger.info(f"Estimates validated on iteration {iteration}")
            break
        else:
            estimate_critique = estimate_check.get("critique", "Please improve the estimates.")
            logger.info(f"Estimates rejected on iteration {iteration}, critique: {estimate_critique[:100]}...")
            
            if iteration < MAX_VALIDATION_ITERATIONS:
                if status_callback:
                    await status_callback(AgentStatusUpdate(
                        active=True,
                        agent=AgentType.ESTIMATOR,
                        message=f"Estimates need improvement, retrying ({iteration}/{MAX_VALIDATION_ITERATIONS})..."
                    ))
    
    if not estimate_valid:
        logger.warning(f"Estimate validation exhausted max iterations ({MAX_VALIDATION_ITERATIONS}), proceeding anyway")
    
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
    
    # Step 5: Run online LLM-as-judge evaluation (async, non-blocking for user)
    if settings.opik_enabled:
        try:
            # Run evaluation in background
            evaluation_results = evaluate_plan_quality(
                topic=topic,
                context=context,
                plan=refined_plan
            )
            logger.info(
                "Plan quality evaluation complete",
                extra={'extra_data': {
                    'overall_score': evaluation_results.get('overall_score'),
                    'structure_score': evaluation_results.get('structure', {}).get('score'),
                    'task_count': len(scheduled_tasks),
                    'total_duration': total_duration
                }}
            )
            
            # Update current trace with evaluation metadata
            if OPIK_AVAILABLE:
                try:
                    opik_context.update_current_trace(
                        metadata={
                            "evaluation": evaluation_results,
                            "task_count": len(scheduled_tasks),
                            "total_duration_hours": total_duration,
                            "phases": list(set(t.phase for t in scheduled_tasks))
                        }
                    )
                except Exception as e:
                    logger.debug(f"Could not update trace metadata: {e}")
        except Exception as e:
            logger.warning(f"Plan evaluation skipped: {e}")
    
    # Clear status
    if status_callback:
        await status_callback(AgentStatusUpdate(
            active=False,
            agent=AgentType.MANAGER,
            message=""
        ))
    
    # Flush all traces to Opik to ensure they're sent
    if settings.opik_enabled:
        flush_traces()
        logger.info(
            f"✅ All traces flushed to Opik",
            extra={'extra_data': {'dashboard_url': get_dashboard_url()}}
        )
    
    return project


def merge_task_updates(existing_tasks: list[Task], updated_plan: dict) -> list[Task]:
    """
    Merge task updates from the Manager with existing tasks.
    
    This ensures that even if the LLM returns partial task data, we preserve
    all fields from the original tasks while applying legitimate changes.
    
    Strategy:
    - Create a lookup of existing tasks by ID
    - For each task in updated_plan:
      - Parse through Pydantic model to normalize values (coerce None to defaults)
      - If ID exists: merge updated fields into existing task
      - If ID is new: add the new task
    - Preserve tasks that weren't modified
    """
    from .output_schemas import TaskOutput
    
    # Create lookup by ID
    existing_by_id = {t.id: t for t in existing_tasks}
    updated_tasks_data = updated_plan.get("tasks", [])
    
    # Track which IDs we've seen in the update
    seen_ids = set()
    result_tasks = []
    
    for ut in updated_tasks_data:
        task_id = ut.get("id", "")
        seen_ids.add(task_id)
        
        # Check if LLM actually provided duration/buffer values (not None)
        raw_duration = ut.get("duration")
        raw_buffer = ut.get("buffer")
        llm_provided_duration = raw_duration is not None and raw_duration > 0
        llm_provided_buffer = raw_buffer is not None
        
        # Normalize through Pydantic for safety
        try:
            normalized = TaskOutput(**ut)
            ut_duration = normalized.duration
            ut_buffer = normalized.buffer
        except Exception as e:
            logger.warning(f"Failed to normalize task {task_id}: {e}")
            ut_duration = raw_duration if raw_duration else 1.0
            ut_buffer = raw_buffer if raw_buffer is not None else 0.0
        
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
            
            # Use LLM values if provided, otherwise preserve existing
            final_duration = ut_duration if llm_provided_duration else existing.duration
            final_buffer = ut_buffer if llm_provided_buffer else existing.buffer
            
            # Log when we're applying a change
            if final_duration != existing.duration:
                logger.info(f"Task {task_id}: duration changing from {existing.duration} to {final_duration}")
            if final_buffer != existing.buffer:
                logger.info(f"Task {task_id}: buffer changing from {existing.buffer} to {final_buffer}")
            
            # Merge task - use new value if provided and valid, else keep existing
            merged_task = Task(
                id=task_id,
                name=ut.get("name") or existing.name,
                phase=ut.get("phase") or existing.phase,
                startOffset=0,  # Will be recalculated by scheduler
                duration=final_duration,
                buffer=final_buffer,
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


@track(
    name="chat_with_manager",
    tags=["manager", "chat", "plan-refinement"],
    capture_input=True,
    capture_output=True
)
async def chat_with_manager(
    project: ProjectData,
    message: str,
    history: list[dict],
    status_callback: Callable[[AgentStatusUpdate], Any] | None = None
) -> dict:
    """
    Handle a chat message with the Project Manager agent.
    Traced with Opik for conversation monitoring.
    
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
