"""
Opik Evaluation Module for Kanso.AI

Provides Datasets, Experiments, and custom metrics for systematic
evaluation of the multi-agent project planning pipeline.

Features:
- Curated benchmark dataset with diverse project requests
- Full-pipeline evaluation (all 6 agents)
- Analyst-only evaluation (clarification quality)
- Custom scoring metrics (heuristic + LLM-as-judge)
- Experiment comparison support for A/B testing

Usage:
    from app.evaluation import seed_benchmark_dataset, run_plan_quality_experiment

    # Step 1: Seed the dataset (once)
    seed_benchmark_dataset()

    # Step 2: Run experiments
    result = await run_plan_quality_experiment("baseline-gemini-pro")
"""

import json
import re
import time
import asyncio
import logging
from typing import Any, Dict, List, Optional

from opik.evaluation.metrics import base_metric
from opik.evaluation.metrics.score_result import ScoreResult

from .config import get_settings
from .logging_config import get_logger
from .opik_service import (
    seed_dataset,
    run_evaluation,
    is_opik_enabled,
    get_or_create_dataset,
)

logger = get_logger(__name__)
settings = get_settings()


def _parse_llm_json(text: str) -> dict:
    """
    Parse JSON from LLM response, handling markdown code blocks.
    
    Gemini often wraps JSON in ```json ... ``` blocks.
    """
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text).strip()
    cleaned = cleaned.rstrip("`").strip()
    return json.loads(cleaned)

# ============================================================================
# Benchmark Dataset
# ============================================================================

BENCHMARK_DATASET_NAME = "kanso-planning-benchmark"
BENCHMARK_DATASET_DESCRIPTION = (
    "Diverse project planning requests for evaluating Kanso.AI's multi-agent pipeline. "
    "Covers simple to complex projects, vague to specific requests, "
    "and multiple domains (web, mobile, data, DevOps, AI)."
)

BENCHMARK_ITEMS: List[Dict[str, Any]] = [
    # --- Simple / Clear Requests ---
    {
        "input": "Build a personal portfolio website with a blog section",
        "context": "I'm a frontend developer with 3 years of experience. I want to use React and deploy on Vercel. Timeline: 2 weeks.",
        "expected_traits": {
            "min_tasks": 3,
            "max_tasks": 8,
            "expected_phases": ["Design", "Development", "Deployment"],
            "complexity": "simple",
            "domain": "web"
        },
        "difficulty": "easy",
        "tags": ["web", "frontend", "clear-request"]
    },
    {
        "input": "Create a REST API for a todo list application",
        "context": "Using Python FastAPI with SQLite database. I'm a backend developer. Need it done in 1 week.",
        "expected_traits": {
            "min_tasks": 3,
            "max_tasks": 7,
            "expected_phases": ["Setup", "Development", "Testing"],
            "complexity": "simple",
            "domain": "backend"
        },
        "difficulty": "easy",
        "tags": ["backend", "api", "clear-request"]
    },

    # --- Medium Complexity ---
    {
        "input": "Build an e-commerce platform with payment processing and inventory management",
        "context": "Small business selling handmade jewelry. Need Stripe integration. Team of 2 developers. Budget for 1 month of development.",
        "expected_traits": {
            "min_tasks": 6,
            "max_tasks": 15,
            "expected_phases": ["Planning", "Design", "Backend", "Frontend", "Integration", "Testing"],
            "complexity": "medium",
            "domain": "fullstack"
        },
        "difficulty": "medium",
        "tags": ["fullstack", "e-commerce", "payments"]
    },
    {
        "input": "Develop a mobile fitness tracking app with social features",
        "context": "React Native for cross-platform. Features: workout logging, progress charts, friend challenges, push notifications. Solo developer, 6 weeks timeline.",
        "expected_traits": {
            "min_tasks": 6,
            "max_tasks": 14,
            "expected_phases": ["Design", "Core Features", "Social Features", "Testing", "Launch"],
            "complexity": "medium",
            "domain": "mobile"
        },
        "difficulty": "medium",
        "tags": ["mobile", "health", "social", "hackathon-theme"]
    },
    {
        "input": "Set up a CI/CD pipeline with automated testing and staging environments",
        "context": "We have a Node.js monorepo with 3 microservices. Currently deploying manually to AWS ECS. Want GitHub Actions for CI and ArgoCD for CD. Team of 3 DevOps engineers.",
        "expected_traits": {
            "min_tasks": 5,
            "max_tasks": 12,
            "expected_phases": ["Assessment", "CI Setup", "CD Setup", "Testing", "Documentation"],
            "complexity": "medium",
            "domain": "devops"
        },
        "difficulty": "medium",
        "tags": ["devops", "ci-cd", "infrastructure"]
    },

    # --- Complex / Large Scope ---
    {
        "input": "Build a real-time collaborative whiteboard application with video chat integration",
        "context": "EdTech startup. Need WebSocket-based real-time drawing, shape tools, text annotations, video/audio via WebRTC, session recording, and export to PDF. Team of 4 developers, 3 month timeline.",
        "expected_traits": {
            "min_tasks": 10,
            "max_tasks": 25,
            "expected_phases": ["Architecture", "Core Canvas", "Real-time Sync", "Video Integration", "Recording", "Testing", "Deployment"],
            "complexity": "complex",
            "domain": "fullstack"
        },
        "difficulty": "hard",
        "tags": ["fullstack", "real-time", "webrtc", "complex"]
    },
    {
        "input": "Design and implement a microservices-based API gateway for a fintech platform",
        "context": "Handling payment processing, KYC verification, and transaction monitoring. Must be PCI-DSS compliant. Using Kubernetes, Istio service mesh. Team of 6, timeline 4 months.",
        "expected_traits": {
            "min_tasks": 10,
            "max_tasks": 25,
            "expected_phases": ["Architecture", "Security", "Core Services", "Compliance", "Integration", "Testing", "Monitoring"],
            "complexity": "complex",
            "domain": "backend"
        },
        "difficulty": "hard",
        "tags": ["backend", "fintech", "security", "microservices"]
    },

    # --- Vague / Ambiguous Requests (tests analyst quality) ---
    {
        "input": "I want to build an app",
        "context": "",
        "expected_traits": {
            "min_tasks": 3,
            "max_tasks": 10,
            "complexity": "unknown",
            "domain": "unknown",
            "should_ask_clarification": True
        },
        "difficulty": "tricky",
        "tags": ["vague", "needs-clarification"]
    },
    {
        "input": "Make something with AI",
        "context": "I know Python",
        "expected_traits": {
            "min_tasks": 3,
            "max_tasks": 10,
            "complexity": "unknown",
            "domain": "ai",
            "should_ask_clarification": True
        },
        "difficulty": "tricky",
        "tags": ["vague", "ai", "needs-clarification"]
    },

    # --- Hackathon Theme Aligned (New Year's resolutions / productivity) ---
    {
        "input": "Build a habit tracker app that helps users stick to their New Year's resolutions",
        "context": "Web app with daily check-ins, streak tracking, motivational reminders, and weekly progress reports. Want to use AI to personalize encouragement messages. Solo developer, 3 weeks.",
        "expected_traits": {
            "min_tasks": 5,
            "max_tasks": 12,
            "expected_phases": ["Design", "Core Tracking", "AI Integration", "Notifications", "Testing"],
            "complexity": "medium",
            "domain": "fullstack"
        },
        "difficulty": "medium",
        "tags": ["productivity", "habits", "ai", "hackathon-theme"]
    },
    {
        "input": "Create an AI-powered daily planner that learns from user productivity patterns",
        "context": "Features: smart task prioritization, time-blocking suggestions, focus mode with Pomodoro timer, end-of-day reflection prompts. Integration with Google Calendar. React + Python backend.",
        "expected_traits": {
            "min_tasks": 6,
            "max_tasks": 14,
            "expected_phases": ["Design", "Backend API", "AI Engine", "Frontend", "Calendar Integration", "Testing"],
            "complexity": "medium",
            "domain": "fullstack"
        },
        "difficulty": "medium",
        "tags": ["productivity", "ai", "planning", "hackathon-theme"]
    },

    # --- Edge Case: Very specific / technical ---
    {
        "input": "Implement a distributed task queue with dead letter handling and priority scheduling using Redis Streams",
        "context": "Python workers consuming from Redis Streams. Need exactly-once processing guarantees, configurable retry policies with exponential backoff, dead letter queue with alerting, priority lanes (high/medium/low), and Prometheus metrics. 2 senior engineers, 2 weeks.",
        "expected_traits": {
            "min_tasks": 5,
            "max_tasks": 12,
            "expected_phases": ["Design", "Core Queue", "DLQ & Retry", "Priority System", "Monitoring", "Testing"],
            "complexity": "complex",
            "domain": "backend"
        },
        "difficulty": "hard",
        "tags": ["backend", "distributed", "redis", "specific"]
    },
]


def seed_benchmark_dataset() -> bool:
    """
    Seed the benchmark dataset in Opik.
    
    This creates (or updates) the evaluation dataset with
    curated project planning requests spanning multiple
    domains and complexity levels.
    
    Returns:
        True if successful, False otherwise
    """
    if not is_opik_enabled():
        logger.warning("Opik not enabled — cannot seed dataset")
        return False
    
    result = seed_dataset(
        dataset_name=BENCHMARK_DATASET_NAME,
        items=BENCHMARK_ITEMS,
        description=BENCHMARK_DATASET_DESCRIPTION,
    )
    
    if result:
        logger.info(
            f"✅ Benchmark dataset seeded: {len(BENCHMARK_ITEMS)} items",
            extra={'extra_data': {
                'dataset': BENCHMARK_DATASET_NAME,
                'items': len(BENCHMARK_ITEMS),
                'difficulties': {
                    'easy': sum(1 for i in BENCHMARK_ITEMS if i.get('difficulty') == 'easy'),
                    'medium': sum(1 for i in BENCHMARK_ITEMS if i.get('difficulty') == 'medium'),
                    'hard': sum(1 for i in BENCHMARK_ITEMS if i.get('difficulty') == 'hard'),
                    'tricky': sum(1 for i in BENCHMARK_ITEMS if i.get('difficulty') == 'tricky'),
                }
            }}
        )
        return True
    return False


# ============================================================================
# Custom Evaluation Metrics (Opik BaseMetric subclasses)
# ============================================================================

class TaskCountReasonableness(base_metric.BaseMetric):
    """
    Heuristic metric: checks if the number of tasks in the plan
    falls within the expected range for the given project complexity.
    
    Score: 1.0 if within range, scaled down proportionally if outside.
    """
    
    def __init__(self):
        super().__init__(name="task_count_reasonableness", track=False)
    
    def score(self, output: str, expected_traits: Any = None, **ignored_kwargs: Any) -> ScoreResult:
        """Score based on whether task count matches expected range."""
        reference = expected_traits or {}
        if isinstance(reference, str):
            try:
                reference = json.loads(reference)
            except (json.JSONDecodeError, TypeError):
                reference = {}
        
        min_tasks = reference.get("min_tasks", 3)
        max_tasks = reference.get("max_tasks", 15)
        
        # Parse output — it's the JSON string of the task result
        plan = {}
        if isinstance(output, str):
            try:
                plan = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                plan = {}
        elif isinstance(output, dict):
            plan = output
        
        # Navigate to tasks
        if "plan" in plan:
            plan = plan["plan"]
        tasks = plan.get("tasks", [])
        task_count = len(tasks)
        
        if task_count == 0:
            return ScoreResult(name=self.name, value=0.0, reason="No tasks generated")
        
        if min_tasks <= task_count <= max_tasks:
            value = 1.0
            reason = f"Task count {task_count} is within expected range [{min_tasks}-{max_tasks}]"
        elif task_count < min_tasks:
            value = max(0.0, task_count / min_tasks)
            reason = f"Task count {task_count} is below minimum {min_tasks}"
        else:
            value = max(0.3, 1.0 - (task_count - max_tasks) / max_tasks)
            reason = f"Task count {task_count} exceeds maximum {max_tasks}"
        
        return ScoreResult(name=self.name, value=round(value, 3), reason=reason)


class PlanHasRequiredFields(base_metric.BaseMetric):
    """
    Heuristic metric: checks that the plan has all required structural fields
    (projectTitle, tasks with ids/names/phases/durations, dependencies, subtasks).
    
    Score: proportion of required fields present.
    """
    
    def __init__(self):
        super().__init__(name="plan_structure_completeness", track=False)
    
    def score(self, output: str, **ignored_kwargs: Any) -> ScoreResult:
        """Check structural completeness of the plan."""
        plan = {}
        if isinstance(output, str):
            try:
                plan = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                plan = {}
        elif isinstance(output, dict):
            plan = output
        
        if "plan" in plan:
            plan = plan["plan"]
        
        checks = {
            "has_title": bool(plan.get("projectTitle") or plan.get("title")),
            "has_tasks": len(plan.get("tasks", [])) > 0,
            "tasks_have_ids": all(t.get("id") for t in plan.get("tasks", [])) if plan.get("tasks") else False,
            "tasks_have_names": all(t.get("name") for t in plan.get("tasks", [])) if plan.get("tasks") else False,
            "tasks_have_phases": all(t.get("phase") for t in plan.get("tasks", [])) if plan.get("tasks") else False,
            "tasks_have_durations": all(
                t.get("duration") is not None and t.get("duration") > 0
                for t in plan.get("tasks", [])
            ) if plan.get("tasks") else False,
            "has_dependencies": any(
                len(t.get("dependencies", [])) > 0
                for t in plan.get("tasks", [])
            ) if plan.get("tasks") else False,
            "has_subtasks": any(
                len(t.get("subtasks", [])) > 0
                for t in plan.get("tasks", [])
            ) if plan.get("tasks") else False,
            "has_summary": bool(plan.get("projectSummary") or plan.get("description")),
        }
        
        passed = sum(1 for v in checks.values() if v)
        total = len(checks)
        value = passed / total
        
        missing = [k for k, v in checks.items() if not v]
        reason = (
            f"All {total} structural checks passed"
            if not missing
            else f"Missing: {', '.join(missing)} ({passed}/{total} passed)"
        )
        
        return ScoreResult(name=self.name, value=round(value, 3), reason=reason)


class DurationRealism(base_metric.BaseMetric):
    """
    Heuristic metric: checks that task durations are realistic.
    
    Rules:
    - No task should be less than 0.5 hours
    - No single task should exceed 80 hours (2 work-weeks)
    - Buffer should not exceed task duration
    """
    
    def __init__(self):
        super().__init__(name="duration_realism", track=False)
    
    def score(self, output: str, **ignored_kwargs: Any) -> ScoreResult:
        """Score duration realism."""
        plan = {}
        if isinstance(output, str):
            try:
                plan = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                plan = {}
        elif isinstance(output, dict):
            plan = output
        
        if "plan" in plan:
            plan = plan["plan"]
        tasks = plan.get("tasks", [])
        
        if not tasks:
            return ScoreResult(name=self.name, value=0.0, reason="No tasks to evaluate")
        
        issues = []
        for t in tasks:
            duration = t.get("duration", 0)
            buffer = t.get("buffer", 0)
            name = t.get("name", "unnamed")
            
            if duration < 0.5:
                issues.append(f"'{name}' has unrealistically short duration ({duration}h)")
            if duration > 80:
                issues.append(f"'{name}' has very long duration ({duration}h)")
            if buffer is not None and buffer > duration:
                issues.append(f"'{name}' buffer ({buffer}h) exceeds duration ({duration}h)")
        
        value = max(0.0, 1.0 - len(issues) / len(tasks))
        reason = (
            f"All {len(tasks)} tasks have realistic durations"
            if not issues
            else f"{len(issues)} issue(s): {'; '.join(issues[:3])}"
        )
        
        return ScoreResult(name=self.name, value=round(value, 3), reason=reason)


class PlanQualityLLMJudge(base_metric.BaseMetric):
    """
    LLM-as-Judge metric: comprehensive plan quality evaluation.
    
    Uses Gemini to evaluate the plan holistically on:
    - Requirement coverage
    - Task granularity
    - Logical dependencies
    - Completeness of subtasks
    """
    
    def __init__(self, model: str = None):
        super().__init__(name="plan_quality_llm_judge", track=False)
        self.model = model or settings.default_model
    
    def score(self, input: str, output: str, context: str = "", **ignored_kwargs: Any) -> ScoreResult:
        """Score using LLM-as-judge evaluation."""
        from google import genai
        
        plan_str = output if isinstance(output, str) else json.dumps(output)
        
        prompt = f"""You are an expert project planning evaluator. Score this project plan on a scale of 0.0 to 1.0.

ORIGINAL REQUEST: {input}
ADDITIONAL CONTEXT: {context}

GENERATED PLAN:
{plan_str[:4000]}

Evaluate these dimensions (equal weight):
1. **Requirement Coverage** (0-0.25): Does the plan address all stated requirements?
2. **Task Granularity** (0-0.25): Are tasks appropriately sized (not too big, not too small)?
3. **Logical Flow** (0-0.25): Are dependencies correct? Is the sequence logical?
4. **Completeness** (0-0.25): Are subtasks comprehensive? Any obvious gaps?

Return ONLY a JSON object:
{{"score": 0.XX, "reasoning": "One-sentence explanation"}}"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            result = _parse_llm_json(response.text)
            return ScoreResult(
                name=self.name,
                value=float(result.get("score", 0.5)),
                reason=result.get("reasoning", "Evaluation completed")
            )
        except Exception as e:
            logger.error(f"LLM judge evaluation failed: {e}")
            return ScoreResult(
                name=self.name,
                value=0.5,
                reason=f"Evaluation error: {str(e)[:100]}"
            )


class ClarificationQualityJudge(base_metric.BaseMetric):
    """
    LLM-as-Judge metric for evaluating analyst clarification quality.
    
    Scores how well the analyst identifies ambiguity and asks
    useful clarifying questions.
    """
    
    def __init__(self, model: str = None):
        super().__init__(name="clarification_quality", track=False)
        self.model = model or settings.default_model
    
    def score(self, input: str, output: str, expected_traits: Any = None, **ignored_kwargs: Any) -> ScoreResult:
        """Score clarification quality."""
        from google import genai
        
        # Parse expected traits
        traits = expected_traits or {}
        if isinstance(traits, str):
            try:
                traits = json.loads(traits)
            except (json.JSONDecodeError, TypeError):
                traits = {}
        
        # Parse output
        result_data = {}
        if isinstance(output, str):
            try:
                result_data = json.loads(output)
            except (json.JSONDecodeError, TypeError):
                result_data = {}
        elif isinstance(output, dict):
            result_data = output
        
        should_clarify = traits.get("should_ask_clarification", False)
        needs_clarification = result_data.get("needsClarification", False)
        questions = result_data.get("questions", [])
        reasoning = result_data.get("reasoning", "")
        
        prompt = f"""You are evaluating an AI analyst agent's ability to identify ambiguity in project requests.

USER REQUEST: "{input}"
EXPECTED TO NEED CLARIFICATION: {should_clarify}

ANALYST OUTPUT:
- Needs Clarification: {needs_clarification}
- Questions Asked: {json.dumps(questions)}
- Reasoning: {reasoning}

Score the analyst on a scale of 0.0 to 1.0:
1. **Correct Detection** (0-0.4): Did it correctly identify whether clarification was needed?
2. **Question Quality** (0-0.3): Are questions specific, actionable, and non-redundant?
3. **Reasoning Quality** (0-0.3): Is the reasoning clear and well-justified?

Return ONLY a JSON object:
{{"score": 0.XX, "reasoning": "One-sentence explanation"}}"""

        try:
            client = genai.Client(api_key=settings.google_api_key)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt
            )
            result = _parse_llm_json(response.text)
            return ScoreResult(
                name=self.name,
                value=float(result.get("score", 0.5)),
                reason=result.get("reasoning", "Evaluation completed")
            )
        except Exception as e:
            logger.error(f"Clarification quality evaluation failed: {e}")
            return ScoreResult(
                name=self.name,
                value=0.5,
                reason=f"Evaluation error: {str(e)[:100]}"
            )


# ============================================================================
# Task Functions (run the actual pipeline for each dataset item)
# ============================================================================

def create_plan_generation_task():
    """
    Create the task function for full pipeline evaluation.
    
    This wraps the async orchestrator in a sync function
    compatible with Opik's evaluate() API.
    
    Returns:
        Callable that takes a dataset item and returns the generated plan
    """
    from .agents.orchestrator import generate_project_plan
    
    def plan_task(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the full multi-agent pipeline on a dataset item.
        
        Returns dict with 'output' key containing JSON-serialized plan.
        Opik merges this with dataset item keys and passes all as kwargs to score().
        """
        input_text = item.get("input", "")
        context = item.get("context", "")
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # We're inside an already-running loop (e.g. FastAPI)
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    project = pool.submit(
                        asyncio.run,
                        generate_project_plan(
                            topic=input_text,
                            context=context,
                            file=None,
                            status_callback=None
                        )
                    ).result(timeout=300)
            else:
                project = loop.run_until_complete(
                    generate_project_plan(
                        topic=input_text,
                        context=context,
                        file=None,
                        status_callback=None
                    )
                )
        except RuntimeError:
            project = asyncio.run(
                generate_project_plan(
                    topic=input_text,
                    context=context,
                    file=None,
                    status_callback=None
                )
            )
        
        # Convert ProjectData to dict for scoring
        plan_dict = project.model_dump(by_alias=True)
        
        # Return 'output' as JSON string — Opik merges task output keys
        # with dataset item keys and passes them as kwargs to score()
        return {
            "output": json.dumps(plan_dict),
        }
    
    return plan_task


def create_analyst_task():
    """
    Create the task function for analyst-only evaluation.
    
    Runs only the Analyst agent to evaluate clarification quality.
    
    Returns:
        Callable that takes a dataset item and returns analyst output
    """
    from .agents.orchestrator import analyze_request
    
    def analyst_task(item: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the analyst agent on a dataset item.
        
        Returns dict with 'output' key containing JSON-serialized analyst result.
        Opik merges this with dataset item keys and passes all as kwargs to score().
        """
        input_text = item.get("input", "")
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    result = pool.submit(
                        asyncio.run,
                        analyze_request(
                            topic=input_text,
                            chat_history=[],
                            status_callback=None
                        )
                    ).result(timeout=120)
            else:
                result = loop.run_until_complete(
                    analyze_request(
                        topic=input_text,
                        chat_history=[],
                        status_callback=None
                    )
                )
        except RuntimeError:
            result = asyncio.run(
                analyze_request(
                    topic=input_text,
                    chat_history=[],
                    status_callback=None
                )
            )
        
        # Return 'output' as JSON string — Opik merges task output keys
        # with dataset item keys and passes them as kwargs to score()
        return {
            "output": json.dumps({
                "needsClarification": result.get("needsClarification", False),
                "questions": result.get("questions", []),
                "reasoning": result.get("reasoning", ""),
                "question_count": len(result.get("questions", [])),
            }),
        }
    
    return analyst_task


# ============================================================================
# Experiment Runners
# ============================================================================

def run_plan_quality_experiment(
    experiment_name: str = None,
    dataset_name: str = None,
) -> Optional[Any]:
    """
    Run the full pipeline quality experiment.
    
    This evaluates Kanso.AI's entire multi-agent pipeline:
    Research → Architect → Reviewer → Estimator → Reviewer → Manager
    
    Args:
        experiment_name: Custom name for the experiment run
        dataset_name: Dataset to evaluate against (default: benchmark)
        
    Returns:
        EvaluationResult or None
    """
    if not is_opik_enabled():
        logger.warning("Opik not enabled — cannot run experiment")
        return None
    
    name = experiment_name or f"plan-quality-{settings.pro_model}-{int(time.time())}"
    ds_name = dataset_name or BENCHMARK_DATASET_NAME
    
    # Metrics: 3 heuristic + 1 LLM-as-judge
    metrics = [
        TaskCountReasonableness(),
        PlanHasRequiredFields(),
        DurationRealism(),
        PlanQualityLLMJudge(),
    ]
    
    task_fn = create_plan_generation_task()
    
    logger.info(f"🚀 Starting plan quality experiment: {name}")
    
    result = run_evaluation(
        dataset_name=ds_name,
        task_fn=task_fn,
        scoring_metrics=metrics,
        experiment_name=name,
        experiment_metadata={
            "experiment_type": "plan_quality",
            "pipeline": "full",
            "agents": ["analyst", "researcher", "architect", "reviewer", "estimator", "manager"],
            "metrics": [m.name for m in metrics],
        }
    )
    
    if result:
        logger.info(f"✅ Plan quality experiment complete: {name}")
    
    return result


def run_analyst_experiment(
    experiment_name: str = None,
    dataset_name: str = None,
) -> Optional[Any]:
    """
    Run the analyst clarification quality experiment.
    
    This evaluates only the Analyst agent's ability to:
    - Detect ambiguous vs. clear requests
    - Ask relevant clarifying questions
    - Provide clear reasoning
    
    Args:
        experiment_name: Custom name for the experiment run
        dataset_name: Dataset to evaluate against (default: benchmark)
        
    Returns:
        EvaluationResult or None
    """
    if not is_opik_enabled():
        logger.warning("Opik not enabled — cannot run experiment")
        return None
    
    name = experiment_name or f"analyst-quality-{settings.pro_model}-{int(time.time())}"
    ds_name = dataset_name or BENCHMARK_DATASET_NAME
    
    metrics = [
        ClarificationQualityJudge(),
    ]
    
    task_fn = create_analyst_task()
    
    logger.info(f"🚀 Starting analyst experiment: {name}")
    
    result = run_evaluation(
        dataset_name=ds_name,
        task_fn=task_fn,
        scoring_metrics=metrics,
        experiment_name=name,
        experiment_metadata={
            "experiment_type": "analyst_quality",
            "pipeline": "analyst_only",
            "agents": ["analyst"],
            "metrics": [m.name for m in metrics],
        }
    )
    
    if result:
        logger.info(f"✅ Analyst experiment complete: {name}")
    
    return result


def get_benchmark_dataset_info() -> Dict[str, Any]:
    """
    Get information about the benchmark dataset.
    
    Returns:
        Dict with dataset metadata and item summaries
    """
    difficulties = {}
    domains = {}
    tags_all = set()
    
    for item in BENCHMARK_ITEMS:
        d = item.get("difficulty", "unknown")
        difficulties[d] = difficulties.get(d, 0) + 1
        
        domain = item.get("expected_traits", {}).get("domain", "unknown")
        domains[domain] = domains.get(domain, 0) + 1
        
        for tag in item.get("tags", []):
            tags_all.add(tag)
    
    return {
        "name": BENCHMARK_DATASET_NAME,
        "description": BENCHMARK_DATASET_DESCRIPTION,
        "total_items": len(BENCHMARK_ITEMS),
        "difficulties": difficulties,
        "domains": domains,
        "all_tags": sorted(tags_all),
        "items_preview": [
            {"input": item["input"][:80], "difficulty": item.get("difficulty")}
            for item in BENCHMARK_ITEMS
        ]
    }
