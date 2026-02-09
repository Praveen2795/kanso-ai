"""
Opik Observability Service for Kanso.AI

Provides comprehensive tracing, evaluation, and monitoring for the multi-agent
project planning system using Comet's Opik platform.

Features:
- Google ADK agent tracing via OpikTracer
- LLM-as-judge evaluations for plan quality
- Custom metrics for agent performance
- Experiment tracking for model comparisons
- Cost and token usage monitoring
- Agent callbacks for detailed tracing
"""

import os
import logging
import time
from typing import Any, Dict, List, Optional
from functools import wraps
from contextlib import contextmanager

from .config import get_settings
from .logging_config import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Opik imports - wrapped in try/except for graceful degradation
_opik_available = False
_opik_client = None
_adk_tracer = None

try:
    import opik
    from opik import track, opik_context
    from opik.integrations.adk import OpikTracer, track_adk_agent_recursive
    _opik_available = True
    logger.info("Opik SDK loaded successfully")
except ImportError as e:
    logger.warning(f"Opik SDK not available: {e}. Observability features disabled.")
    # Create dummy decorators for graceful degradation
    def track(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args or callable(args[0]) else decorator
    
    class opik_context:
        @staticmethod
        def update_current_span(*args, **kwargs):
            pass
        @staticmethod
        def update_current_trace(*args, **kwargs):
            pass
    
    class OpikTracer:
        def __init__(self, *args, **kwargs):
            pass
    
    def track_adk_agent_recursive(agent, tracer):
        return agent


def configure_opik() -> bool:
    """
    Configure Opik with API credentials from environment.
    
    This should be called once at application startup.
    
    Returns:
        True if Opik is configured successfully, False otherwise.
    """
    global _opik_client, _opik_available
    
    if not _opik_available:
        logger.warning("Opik SDK not installed. Run: pip install opik")
        return False
    
    if not settings.opik_enabled:
        logger.warning(
            "Opik not configured. Set OPIK_API_KEY and OPIK_WORKSPACE in .env"
        )
        return False
    
    try:
        opik.configure(
            api_key=settings.opik_api_key,
            workspace=settings.opik_workspace,
        )
        
        # Set project name in environment for ADK integration
        os.environ["OPIK_PROJECT_NAME"] = settings.opik_project_name
        
        _opik_client = opik.Opik()
        logger.info(
            f"✅ Opik configured successfully for project: {settings.opik_project_name}",
            extra={'extra_data': {
                'workspace': settings.opik_workspace,
                'project': settings.opik_project_name
            }}
        )
        print(f"✅ Opik configured for workspace: {settings.opik_workspace}")
        print(f"✅ Opik project: {settings.opik_project_name}")
        return True
    except Exception as e:
        logger.error(f"Failed to configure Opik: {e}")
        return False


def flush_traces():
    """
    Flush all pending traces to Opik.
    
    Call this at the end of request processing or before shutdown
    to ensure all traces are sent to the Opik dashboard.
    """
    if _opik_available:
        try:
            opik.flush_tracker()
            logger.debug("Opik traces flushed successfully")
        except Exception as e:
            logger.warning(f"Failed to flush Opik traces: {e}")


def get_opik_client():
    """Get the configured Opik client."""
    return _opik_client


def create_adk_tracer(
    name: str = "kanso-ai-agent",
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> OpikTracer:
    """
    Create an OpikTracer for Google ADK agent tracing.
    
    Args:
        name: Name for the trace
        tags: Optional tags for filtering
        metadata: Optional metadata for context
        
    Returns:
        Configured OpikTracer instance
    """
    default_tags = ["kanso-ai", "project-planning", "multi-agent"]
    default_metadata = {
        "environment": settings.environment,
        "model": settings.default_model,
        "framework": "google-adk",
        "app_version": "1.0.0"
    }
    
    return OpikTracer(
        name=name,
        tags=(tags or []) + default_tags,
        metadata={**default_metadata, **(metadata or {})},
        project_name=settings.opik_project_name
    )


def instrument_agent(agent, tracer: Optional[OpikTracer] = None):
    """
    Instrument an ADK agent with Opik tracing.
    
    Args:
        agent: The ADK agent to instrument
        tracer: Optional pre-configured tracer
        
    Returns:
        The instrumented agent
    """
    if not _opik_available or not settings.opik_enabled:
        return agent
    
    if tracer is None:
        tracer = create_adk_tracer(name=getattr(agent, 'name', 'unknown-agent'))
    
    return track_adk_agent_recursive(agent, tracer)


# ============================================================================
# Tracking Decorators (following commit-coach patterns)
# ============================================================================

def track_agent_run(agent_name: str):
    """
    Decorator to track agent runs with Opik.
    
    Similar to commit-coach pattern for consistent tracing across projects.
    
    Args:
        agent_name: Name of the agent being tracked
        
    Returns:
        Decorated function with Opik tracing
    """
    def decorator(func):
        @wraps(func)
        @track(name=f"agent_run_{agent_name}", tags=["adk", "agent", "kanso-ai"])
        async def wrapper(*args, **kwargs):
            # Add metadata about the agent
            if _opik_available:
                try:
                    opik_context.update_current_span(
                        metadata={
                            "agent_name": agent_name,
                            "model": settings.default_model,
                            "framework": "google-adk"
                        }
                    )
                except Exception:
                    pass
            return await func(*args, **kwargs)
        return wrapper
    return decorator


def track_tool_call(tool_name: str):
    """
    Decorator to track tool calls with Opik.
    
    Args:
        tool_name: Name of the tool being tracked
        
    Returns:
        Decorated function with Opik tracing
    """
    def decorator(func):
        @wraps(func)
        @track(name=f"tool_{tool_name}", tags=["adk", "tool", "kanso-ai"])
        def wrapper(*args, **kwargs):
            if _opik_available:
                try:
                    opik_context.update_current_span(
                        metadata={"tool_name": tool_name}
                    )
                except Exception:
                    pass
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================================
# Custom Callbacks for ADK Agents
# ============================================================================

def opik_before_agent_callback(agent_name: str, invocation_context: dict) -> None:
    """
    Callback to run before an agent starts processing.
    
    This can be used with ADK's before_agent_callback parameter
    to add detailed tracing metadata.
    """
    if not _opik_available or not settings.opik_enabled:
        return
        
    try:
        opik_context.update_current_trace(
            tags=[agent_name, "adk-agent", "kanso-ai"],
            metadata={
                "agent_started": agent_name,
                "context": str(invocation_context)[:500],  # Truncate for safety
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }
        )
    except Exception as e:
        logger.debug(f"Failed to update trace in before_agent_callback: {e}")


def opik_after_agent_callback(agent_name: str, result: str) -> None:
    """
    Callback to run after an agent completes processing.
    
    This can be used with ADK's after_agent_callback parameter.
    """
    if not _opik_available or not settings.opik_enabled:
        return
        
    try:
        opik_context.update_current_trace(
            metadata={
                "agent_completed": agent_name,
                "result_length": len(result) if result else 0,
                "completed_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
            }
        )
    except Exception as e:
        logger.debug(f"Failed to update trace in after_agent_callback: {e}")


# ============================================================================
# Custom Evaluation Metrics for Project Plans
# ============================================================================

class PlanStructureScore:
    """
    Custom metric to evaluate the structural quality of a project plan.
    
    Checks for:
    - Logical task dependencies
    - Appropriate task granularity
    - Phase organization
    - Completeness of subtasks
    """
    
    name = "plan_structure_score"
    
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
    
    def score(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Score the structural quality of a plan."""
        from google import genai
        
        prompt = f"""Evaluate the structural quality of this project plan on a scale of 0.0 to 1.0.

PROJECT PLAN:
{plan}

Evaluate based on these criteria:
1. Logical Dependencies: Are task dependencies correctly ordered? (0-0.25)
2. Task Granularity: Are tasks appropriately sized (not too big, not too small)? (0-0.25)
3. Phase Organization: Are phases logically grouped and sequenced? (0-0.25)
4. Completeness: Are subtasks comprehensive for each task? (0-0.25)

Return ONLY a JSON object with this exact format:
{{"score": 0.XX, "reasoning": "Brief explanation"}}"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            import json
            result = json.loads(response.text)
            return {
                "name": self.name,
                "score": float(result.get("score", 0.5)),
                "reason": result.get("reasoning", "Unable to evaluate")
            }
        except Exception as e:
            logger.error(f"Plan structure evaluation failed: {e}")
            return {
                "name": self.name,
                "score": 0.5,
                "reason": f"Evaluation failed: {str(e)}"
            }


class EstimateReasonablenessScore:
    """
    Custom metric to evaluate if time estimates are reasonable.
    
    Checks for:
    - Realistic durations
    - Appropriate buffer times
    - Consistency between complexity and duration
    """
    
    name = "estimate_reasonableness_score"
    
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
    
    def score(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """Score the reasonableness of time estimates."""
        from google import genai
        
        prompt = f"""Evaluate the reasonableness of time estimates in this project plan on a scale of 0.0 to 1.0.

PROJECT PLAN:
{plan}

Evaluate based on these criteria:
1. Duration Realism: Are individual task durations realistic for typical execution? (0-0.33)
2. Buffer Appropriateness: Are buffer times reasonable (not excessive, not missing)? (0-0.33)
3. Complexity Alignment: Do durations match task complexity levels? (0-0.34)

Return ONLY a JSON object with this exact format:
{{"score": 0.XX, "reasoning": "Brief explanation"}}"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            import json
            result = json.loads(response.text)
            return {
                "name": self.name,
                "score": float(result.get("score", 0.5)),
                "reason": result.get("reasoning", "Unable to evaluate")
            }
        except Exception as e:
            logger.error(f"Estimate evaluation failed: {e}")
            return {
                "name": self.name,
                "score": 0.5,
                "reason": f"Evaluation failed: {str(e)}"
            }


class PlanCompletenessScore:
    """
    Custom metric to evaluate plan completeness relative to the original request.
    
    Checks for:
    - Coverage of all requirements
    - Missing critical tasks
    - Alignment with user goals
    """
    
    name = "plan_completeness_score"
    
    def __init__(self, model: str = "gemini-2.5-flash"):
        self.model = model
    
    def score(
        self,
        original_request: str,
        plan: Dict[str, Any],
        context: str = ""
    ) -> Dict[str, Any]:
        """Score how completely the plan addresses the request."""
        from google import genai
        
        prompt = f"""Evaluate how completely this project plan addresses the original request on a scale of 0.0 to 1.0.

ORIGINAL REQUEST:
{original_request}

ADDITIONAL CONTEXT:
{context}

PROJECT PLAN:
{plan}

Evaluate based on these criteria:
1. Requirement Coverage: Does the plan address all stated requirements? (0-0.4)
2. Goal Alignment: Does the plan lead to achieving the user's goals? (0-0.3)
3. Missing Tasks: Are there any obvious missing tasks or phases? (0-0.3)

Return ONLY a JSON object with this exact format:
{{"score": 0.XX, "reasoning": "Brief explanation"}}"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            import json
            result = json.loads(response.text)
            return {
                "name": self.name,
                "score": float(result.get("score", 0.5)),
                "reason": result.get("reasoning", "Unable to evaluate")
            }
        except Exception as e:
            logger.error(f"Completeness evaluation failed: {e}")
            return {
                "name": self.name,
                "score": 0.5,
                "reason": f"Evaluation failed: {str(e)}"
            }


# ============================================================================
# Online Evaluation Functions
# ============================================================================

@track(name="evaluate_plan_quality", tags=["evaluation", "llm-as-judge"])
def evaluate_plan_quality(
    topic: str,
    context: str,
    plan: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Run online LLM-as-judge evaluations on a generated plan.
    
    This is called after plan generation to score the output quality
    and track metrics in Opik.
    
    Args:
        topic: Original project topic
        context: User's clarification context
        plan: The generated project plan
        
    Returns:
        Dict with evaluation scores and feedback
    """
    if not _opik_available or not settings.opik_enabled:
        return {"evaluations_skipped": True, "reason": "Opik not configured"}
    
    try:
        # Initialize metrics
        structure_metric = PlanStructureScore()
        estimate_metric = EstimateReasonablenessScore()
        completeness_metric = PlanCompletenessScore()
        
        # Run evaluations
        structure_result = structure_metric.score(plan)
        estimate_result = estimate_metric.score(plan)
        completeness_result = completeness_metric.score(topic, plan, context)
        
        # Calculate overall score
        overall_score = (
            structure_result["score"] * 0.3 +
            estimate_result["score"] * 0.3 +
            completeness_result["score"] * 0.4
        )
        
        evaluation_results = {
            "overall_score": round(overall_score, 3),
            "structure": structure_result,
            "estimates": estimate_result,
            "completeness": completeness_result,
            "evaluated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
        }
        
        # Log scores to current trace if available
        if _opik_available:
            try:
                opik_context.update_current_trace(
                    feedback_scores=[
                        {"name": "overall_quality", "value": overall_score},
                        {"name": "structure_quality", "value": structure_result["score"]},
                        {"name": "estimate_quality", "value": estimate_result["score"]},
                        {"name": "completeness", "value": completeness_result["score"]},
                    ]
                )
            except Exception as e:
                logger.debug(f"Could not update trace with scores: {e}")
        
        logger.info(
            "Plan evaluation complete",
            extra={'extra_data': {
                'overall_score': overall_score,
                'structure_score': structure_result["score"],
                'estimate_score': estimate_result["score"],
                'completeness_score': completeness_result["score"]
            }}
        )
        
        return evaluation_results
        
    except Exception as e:
        logger.error(f"Plan evaluation failed: {e}", exc_info=True)
        return {
            "evaluations_skipped": True,
            "reason": str(e)
        }


# ============================================================================
# Performance Tracking Decorators
# ============================================================================

def track_agent_performance(agent_name: str, agent_type: str):
    """
    Decorator to track agent performance metrics.
    
    Tracks:
    - Execution time
    - Success/failure rate
    - Output size
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            output_size = 0
            error_msg = None
            
            try:
                result = await func(*args, **kwargs)
                success = True
                if isinstance(result, dict):
                    output_size = len(str(result))
                return result
            except Exception as e:
                error_msg = str(e)
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                
                # Log to Opik if available
                if _opik_available and settings.opik_enabled:
                    try:
                        opik_context.update_current_span(
                            metadata={
                                "agent_name": agent_name,
                                "agent_type": agent_type,
                                "duration_ms": round(duration_ms, 2),
                                "success": success,
                                "output_size": output_size,
                                "error": error_msg
                            }
                        )
                    except Exception:
                        pass
                
                logger.info(
                    f"Agent {agent_name} completed",
                    extra={'extra_data': {
                        'agent': agent_name,
                        'type': agent_type,
                        'duration_ms': round(duration_ms, 2),
                        'success': success
                    }}
                )
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = False
            
            try:
                result = func(*args, **kwargs)
                success = True
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Agent {agent_name} completed",
                    extra={'extra_data': {
                        'agent': agent_name,
                        'duration_ms': round(duration_ms, 2),
                        'success': success
                    }}
                )
        
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper
    
    return decorator


# ============================================================================
# Experiment Tracking
# ============================================================================

def create_experiment(
    name: str,
    description: str = "",
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Any]:
    """
    Create an Opik experiment for A/B testing or model comparison.
    
    Args:
        name: Experiment name
        description: Description of the experiment
        metadata: Additional metadata
        
    Returns:
        Opik experiment object or None if unavailable
    """
    if not _opik_available or not settings.opik_enabled or not _opik_client:
        return None
    
    try:
        return _opik_client.create_experiment(
            name=name,
            dataset_name=None,  # Online experiment
            metadata={
                "description": description,
                "environment": settings.environment,
                **(metadata or {})
            }
        )
    except Exception as e:
        logger.error(f"Failed to create experiment: {e}")
        return None


# ============================================================================
# Utility Functions
# ============================================================================

def log_feedback(
    trace_id: str,
    score: float,
    category: str = "user_feedback",
    comment: str = ""
):
    """
    Log user feedback to a specific trace.
    
    Args:
        trace_id: The trace ID to attach feedback to
        score: Feedback score (0.0 to 1.0)
        category: Feedback category
        comment: Optional user comment
    """
    if not _opik_available or not settings.opik_enabled or not _opik_client:
        return
    
    try:
        _opik_client.log_traces_feedback(
            trace_ids=[trace_id],
            scores=[{
                "name": category,
                "value": score,
                "reason": comment
            }]
        )
        logger.info(f"Logged feedback for trace {trace_id}: {category}={score}")
    except Exception as e:
        logger.error(f"Failed to log feedback: {e}")


def log_agent_feedback(
    trace_id: str,
    score: float,
    feedback_type: str = "quality",
    comment: Optional[str] = None
) -> None:
    """
    Log feedback for an agent interaction.
    
    This follows the commit-coach pattern for consistent feedback logging.
    
    Args:
        trace_id: The Opik trace ID
        score: Score between 0 and 1
        feedback_type: Type of feedback (quality, relevance, accuracy)
        comment: Optional comment
    """
    if not _opik_available or not settings.opik_enabled or not _opik_client:
        return
        
    try:
        _opik_client.log_traces_feedback(
            scores=[
                {
                    "trace_id": trace_id,
                    "name": feedback_type,
                    "value": score,
                    "reason": comment,
                }
            ]
        )
        logger.info(f"Logged agent feedback: {feedback_type}={score} for trace {trace_id}")
    except Exception as e:
        logger.error(f"Failed to log agent feedback: {e}")


def get_trace_url(trace_id: str) -> Optional[str]:
    """
    Get the Opik dashboard URL for a trace.
    
    Args:
        trace_id: The trace ID
        
    Returns:
        URL string or None
    """
    if not settings.opik_enabled:
        return None
    
    return f"https://www.comet.com/opik/{settings.opik_workspace}/{settings.opik_project_name}/traces/{trace_id}"


def get_dashboard_url() -> str:
    """
    Get the Opik dashboard URL for the current project.
    
    Returns:
        Dashboard URL string
    """
    return f"https://www.comet.com/opik/{settings.opik_workspace}/{settings.opik_project_name}"


def is_opik_enabled() -> bool:
    """Check if Opik is available and enabled."""
    return _opik_available and settings.opik_enabled


# ============================================================================
# Dataset & Experiment Management
# ============================================================================

def get_or_create_dataset(
    name: str,
    description: str = ""
) -> Optional[Any]:
    """
    Get or create an Opik dataset for evaluation.
    
    Args:
        name: Dataset name
        description: Dataset description
        
    Returns:
        Opik Dataset object or None
    """
    if not _opik_available or not settings.opik_enabled or not _opik_client:
        logger.warning("Opik not available for dataset creation")
        return None
    
    try:
        dataset = _opik_client.get_or_create_dataset(
            name=name,
            description=description
        )
        logger.info(f"Dataset ready: {name}")
        return dataset
    except Exception as e:
        logger.error(f"Failed to get/create dataset '{name}': {e}")
        return None


def seed_dataset(
    dataset_name: str,
    items: List[Dict[str, Any]],
    description: str = ""
) -> Optional[Any]:
    """
    Seed an Opik dataset with evaluation items.
    
    Each item should have at minimum:
      - input: the project description / prompt
      - expected_output: expected traits or reference data
    
    Args:
        dataset_name: Name for the dataset
        items: List of dicts with evaluation data
        description: Dataset description
        
    Returns:
        Opik Dataset object or None
    """
    dataset = get_or_create_dataset(dataset_name, description)
    if dataset is None:
        return None
    
    try:
        dataset.insert(items)
        logger.info(f"Seeded dataset '{dataset_name}' with {len(items)} items")
        return dataset
    except Exception as e:
        logger.error(f"Failed to seed dataset '{dataset_name}': {e}")
        return None


def run_evaluation(
    dataset_name: str,
    task_fn,
    scoring_metrics: List[Any],
    experiment_name: str = "kanso-eval",
    experiment_metadata: Optional[Dict[str, Any]] = None
) -> Optional[Any]:
    """
    Run an Opik evaluation experiment against a dataset.
    
    This is the core evaluation runner that:
    1. Loads the named dataset
    2. Runs the task function on each dataset item
    3. Scores results with the provided metrics
    4. Logs everything to Opik as an Experiment
    
    Args:
        dataset_name: Name of the Opik dataset to evaluate against
        task_fn: Callable that takes a dataset item dict and returns an output dict
        scoring_metrics: List of Opik metric instances
        experiment_name: Name for the experiment run
        experiment_metadata: Optional metadata dict
        
    Returns:
        EvaluationResult object or None
    """
    if not _opik_available or not settings.opik_enabled or not _opik_client:
        logger.warning("Opik not available for evaluation")
        return None
    
    try:
        from opik.evaluation import evaluate
        
        dataset = _opik_client.get_or_create_dataset(name=dataset_name)
        
        metadata = {
            "project": "kanso-ai",
            "environment": settings.environment,
            "model": settings.default_model,
            "pro_model": settings.pro_model,
            **(experiment_metadata or {})
        }
        
        logger.info(
            f"Starting experiment '{experiment_name}' on dataset '{dataset_name}'",
            extra={'extra_data': {
                'metrics_count': len(scoring_metrics),
                'metric_names': [getattr(m, 'name', type(m).__name__) for m in scoring_metrics]
            }}
        )
        
        result = evaluate(
            experiment_name=experiment_name,
            dataset=dataset,
            task=task_fn,
            scoring_metrics=scoring_metrics,
            experiment_config=metadata,
            project_name=settings.opik_project_name,
        )
        
        logger.info(f"Experiment '{experiment_name}' complete")
        return result
        
    except Exception as e:
        logger.error(f"Evaluation experiment failed: {e}", exc_info=True)
        return None


# Initialize Opik on module load if configured
if settings.opik_enabled:
    configure_opik()
