#!/usr/bin/env python3
"""
Kanso.AI Prompt Optimizer

Uses Opik Agent Optimizer to automatically improve agent prompts
using the benchmark evaluation dataset and custom metrics.

Optimizes:
- Analyst Agent: system prompt for better clarification detection
- Architect Agent: system prompt for better plan structure

Prerequisites:
    pip install opik-optimizer

Usage:
    uv run python optimize_prompts.py --agent analyst --trials 3
    uv run python optimize_prompts.py --agent architect --trials 3
    uv run python optimize_prompts.py --agent analyst --dry-run
"""

import argparse
import json
import sys
import asyncio
from typing import Any, Dict

from app.config import get_settings
from app.opik_service import configure_opik, is_opik_enabled
from app.evaluation import (
    BENCHMARK_DATASET_NAME,
    BENCHMARK_ITEMS,
    seed_benchmark_dataset,
    ClarificationQualityJudge,
)

settings = get_settings()


# ============================================================================
# Analyst Prompt Optimization
# ============================================================================

ANALYST_INITIAL_PROMPT = f"""You are the ANALYST Agent. Your goal is to deeply understand the user's project request.

Your responsibilities:
1. **Verify Technical Terms**: Check if technical terms exist and are correctly used.
2. **Identify Ambiguity**: If context is missing (skill level, deadline, scale), ask for it.

Generate 2-3 **SMART** questions if clarification is needed:
- Specific: Target exact missing information
- Measurable: Can be quantified or clearly answered
- Achievable: Within the user's likely knowledge
- Relevant: Directly impacts project planning
- Time-bound: If deadlines are unclear

If the request is clear and complete, set needsClarification to false.

Respond with JSON containing: needsClarification (bool), questions (list), reasoning (string).

User request: {{question}}"""


def analyst_metric(item: Dict[str, Any], output: str) -> float:
    """
    Metric for analyst prompt optimization.
    
    Evaluates clarification quality using our custom LLM judge.
    Returns a score from 0.0 to 1.0.
    """
    judge = ClarificationQualityJudge()
    
    expected_traits = item.get("expected_traits", {})
    if isinstance(expected_traits, str):
        try:
            expected_traits = json.loads(expected_traits)
        except (json.JSONDecodeError, TypeError):
            expected_traits = {}
    
    try:
        result = judge.score(
            input=item.get("question", item.get("input", "")),
            output=output,
            expected_traits=expected_traits,
        )
        return result.value
    except Exception as e:
        print(f"   ⚠️ Metric error: {e}")
        return 0.5


def run_analyst_optimization(
    max_trials: int = 3,
    n_samples: int = 6,
    dry_run: bool = False,
) -> None:
    """Run Opik Optimizer on the analyst prompt."""
    from opik_optimizer import MetaPromptOptimizer, ChatPrompt
    import opik
    
    client = opik.Opik()
    
    # Use a subset of the benchmark items focused on clarification
    dataset = client.get_or_create_dataset(name="analyst-optimization")
    dataset.insert([
        {
            "question": item["input"],
            "expected_traits": json.dumps(item.get("expected_traits", {})),
        }
        for item in BENCHMARK_ITEMS
    ])
    
    print(f"   Dataset: analyst-optimization ({len(BENCHMARK_ITEMS)} items)")
    
    # Build the prompt to optimize
    prompt = ChatPrompt(
        messages=[
            {"role": "system", "content": ANALYST_INITIAL_PROMPT},
            {"role": "user", "content": "{question}"},
        ],
        model=f"gemini/{settings.pro_model}",
    )
    
    if dry_run:
        print(f"   [DRY RUN] Would optimize analyst prompt with {max_trials} trials")
        print(f"   Initial prompt preview: {ANALYST_INITIAL_PROMPT[:200]}...")
        return
    
    # Run the optimizer
    optimizer = MetaPromptOptimizer(
        model=f"gemini/{settings.pro_model}",
    )
    
    result = optimizer.optimize_prompt(
        prompt=prompt,
        dataset=dataset,
        metric=analyst_metric,
        max_trials=max_trials,
        n_samples=n_samples,
    )
    
    result.display()
    
    print("\n" + "=" * 60)
    print("📝 Optimized Prompt:")
    print("=" * 60)
    if hasattr(result, "best_prompt"):
        print(result.best_prompt)
    elif hasattr(result, "prompt"):
        print(result.prompt)
    print("=" * 60)


# ============================================================================
# Architect Prompt Optimization  
# ============================================================================

ARCHITECT_INITIAL_PROMPT = """You are the ARCHITECT Agent.
Goal: Create the STRUCTURAL BACKBONE of a project plan.

**Instructions:**
1. **Research**: Find best practices and workflows for the project type.
2. **Breakdown**: Create a hierarchical structure:
   - Phases: Major milestones or stages
   - Tasks: Actionable work items within each phase
   - Subtasks: Each Task MUST have at least 3-5 concrete subtasks
3. **Dependencies**: Define logical order (Task B depends on Task A).
4. **Task IDs**: Use descriptive IDs like "phase1_task1", "design_wireframes".
5. **Output**: Return JSON with projectTitle, projectSummary, assumptions, and tasks array.

Each task needs: id, name, phase, duration (placeholder), buffer (0), startOffset (0),
dependencies (list of task ids), description, complexity (Low/Medium/High), subtasks.

User request: {question}
Context: {context}"""


def architect_metric(item: Dict[str, Any], output: str) -> float:
    """
    Metric for architect prompt optimization.
    
    Evaluates plan structure quality using heuristic checks.
    """
    from app.evaluation import PlanHasRequiredFields, TaskCountReasonableness
    
    structure_metric = PlanHasRequiredFields()
    count_metric = TaskCountReasonableness()
    
    expected_traits = item.get("expected_traits", {})
    if isinstance(expected_traits, str):
        try:
            expected_traits = json.loads(expected_traits)
        except (json.JSONDecodeError, TypeError):
            expected_traits = {}
    
    try:
        structure_score = structure_metric.score(output=output)
        count_score = count_metric.score(
            output=output, expected_traits=expected_traits
        )
        # Weighted average: 60% structure, 40% task count
        combined = 0.6 * structure_score.value + 0.4 * count_score.value
        return combined
    except Exception as e:
        print(f"   ⚠️ Metric error: {e}")
        return 0.5


def run_architect_optimization(
    max_trials: int = 3,
    n_samples: int = 6,
    dry_run: bool = False,
) -> None:
    """Run Opik Optimizer on the architect prompt."""
    from opik_optimizer import MetaPromptOptimizer, ChatPrompt
    import opik
    
    client = opik.Opik()
    
    dataset = client.get_or_create_dataset(name="architect-optimization")
    dataset.insert([
        {
            "question": item["input"],
            "context": item.get("context", ""),
            "expected_traits": json.dumps(item.get("expected_traits", {})),
        }
        for item in BENCHMARK_ITEMS
    ])
    
    print(f"   Dataset: architect-optimization ({len(BENCHMARK_ITEMS)} items)")
    
    prompt = ChatPrompt(
        messages=[
            {"role": "system", "content": ARCHITECT_INITIAL_PROMPT},
            {"role": "user", "content": "{question}\nContext: {context}"},
        ],
        model=f"gemini/{settings.pro_model}",
    )
    
    if dry_run:
        print(f"   [DRY RUN] Would optimize architect prompt with {max_trials} trials")
        print(f"   Initial prompt preview: {ARCHITECT_INITIAL_PROMPT[:200]}...")
        return
    
    optimizer = MetaPromptOptimizer(
        model=f"gemini/{settings.pro_model}",
    )
    
    result = optimizer.optimize_prompt(
        prompt=prompt,
        dataset=dataset,
        metric=architect_metric,
        max_trials=max_trials,
        n_samples=n_samples,
    )
    
    result.display()
    
    print("\n" + "=" * 60)
    print("📝 Optimized Prompt:")
    print("=" * 60)
    if hasattr(result, "best_prompt"):
        print(result.best_prompt)
    elif hasattr(result, "prompt"):
        print(result.prompt)
    print("=" * 60)


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Kanso.AI Prompt Optimizer — Opik Agent Optimizer",
    )
    parser.add_argument(
        "--agent",
        choices=["analyst", "architect"],
        required=True,
        help="Which agent's prompt to optimize",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=3,
        help="Number of optimization trials (default: 3)",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=6,
        help="Number of dataset samples per trial (default: 6)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show configuration without running optimization",
    )
    args = parser.parse_args()
    
    if not is_opik_enabled():
        print("❌ Opik is not configured. Set OPIK_API_KEY and OPIK_WORKSPACE in .env")
        sys.exit(1)
    
    configure_opik()
    
    # Seed benchmark dataset (needed for metrics)
    print()
    print("=" * 60)
    print(f"🧬 Opik Agent Optimizer — {args.agent.title()} Agent")
    print("=" * 60)
    print(f"   Trials: {args.trials}")
    print(f"   Samples per trial: {args.samples}")
    print(f"   Model: gemini/{settings.pro_model}")
    print()
    
    seed_benchmark_dataset()
    
    if args.agent == "analyst":
        run_analyst_optimization(
            max_trials=args.trials,
            n_samples=args.samples,
            dry_run=args.dry_run,
        )
    elif args.agent == "architect":
        run_architect_optimization(
            max_trials=args.trials,
            n_samples=args.samples,
            dry_run=args.dry_run,
        )
    
    print()
    print("📊 View optimization results in Opik Dashboard:")
    print(f"   https://www.comet.com/opik/{settings.opik_workspace}/{settings.opik_project_name}")


if __name__ == "__main__":
    main()
