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
)

settings = get_settings()


# ============================================================================
# Analyst Prompt Optimization
# ============================================================================

ANALYST_INITIAL_PROMPT = """You are the ANALYST Agent. Your goal is to deeply understand the user's project request.

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

User request: {question}"""


def analyst_metric(dataset_item: Dict[str, Any], llm_output: str) -> float:
    """
    Fast, deterministic metric for analyst prompt optimization.
    
    Evaluates clarification quality using heuristic checks (no LLM API calls)
    so the optimizer can run quickly through many trials.
    
    Scores:
    - JSON structure (needsClarification, questions, reasoning)  — 0.25
    - Question quality (count, specificity, non-trivial)         — 0.35
    - Reasoning presence and quality                             — 0.20
    - Alignment with expected traits                             — 0.20
    
    Returns a score from 0.0 to 1.0.
    """
    import re
    
    expected_traits = dataset_item.get("expected_traits", {})
    if isinstance(expected_traits, str):
        try:
            expected_traits = json.loads(expected_traits)
        except (json.JSONDecodeError, TypeError):
            expected_traits = {}
    
    score = 0.0
    output = llm_output.strip() if llm_output else ""
    
    if not output:
        return 0.0
    
    # --- 1. JSON structure (0.25) ---
    parsed = None
    try:
        # Handle markdown-wrapped JSON
        cleaned = re.sub(r"```(?:json)?\s*", "", output).strip().rstrip("`").strip()
        parsed = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        # Try to find JSON block in the text
        json_match = re.search(r'\{[^{}]*"needsClarification"[^{}]*\}', output, re.DOTALL)
        if json_match:
            try:
                parsed = json.loads(json_match.group())
            except (json.JSONDecodeError, TypeError):
                pass
    
    if parsed and isinstance(parsed, dict):
        has_clarification = "needsClarification" in parsed or "needs_clarification" in parsed
        has_questions = "questions" in parsed and isinstance(parsed.get("questions"), list)
        has_reasoning = "reasoning" in parsed and bool(parsed.get("reasoning"))
        json_score = (0.10 if has_clarification else 0.0) + \
                     (0.10 if has_questions else 0.0) + \
                     (0.05 if has_reasoning else 0.0)
        score += json_score
    else:
        # Even without JSON, award partial credit if output discusses clarification
        if any(kw in output.lower() for kw in ["clarif", "question", "need more info", "ambiguous"]):
            score += 0.08
    
    # --- 2. Question quality (0.35) ---
    questions = []
    if parsed and isinstance(parsed.get("questions"), list):
        questions = parsed["questions"]
    else:
        # Extract questions from raw text using ? markers
        questions = re.findall(r'[^.!?]*\?', output)
    
    if questions:
        # Count: 2-4 questions is ideal
        n_q = len(questions)
        count_score = 0.10 if 2 <= n_q <= 4 else (0.06 if 1 <= n_q <= 6 else 0.03)
        score += count_score
        
        # Specificity: questions should be > 15 chars (not too generic)
        specific_count = sum(1 for q in questions if len(str(q)) > 15)
        specificity_score = 0.15 * (specific_count / max(len(questions), 1))
        score += specificity_score
        
        # Non-trivial: questions should contain domain-relevant words
        domain_words = ["tech", "stack", "framework", "deadline", "scale", "user",
                       "database", "deploy", "team", "budget", "feature", "experience",
                       "target", "audience", "requirement", "integration", "performance"]
        relevant_count = sum(
            1 for q in questions
            if any(w in str(q).lower() for w in domain_words)
        )
        relevance_score = 0.10 * (relevant_count / max(len(questions), 1))
        score += relevance_score
    
    # --- 3. Reasoning quality (0.20) ---
    reasoning = ""
    if parsed and isinstance(parsed, dict):
        reasoning = str(parsed.get("reasoning", ""))
    
    if not reasoning and len(output) > 100:
        # Look for reasoning-like text in raw output
        reasoning = output
    
    if reasoning:
        # Reasoning should be substantive (> 30 chars)
        if len(reasoning) > 30:
            score += 0.12
        elif len(reasoning) > 10:
            score += 0.06
        # Reasoning should mention the project topic
        question_text = dataset_item.get("question", "").lower()
        topic_words = [w for w in question_text.split() if len(w) > 3]
        if topic_words and any(w in reasoning.lower() for w in topic_words[:5]):
            score += 0.08
    
    # --- 4. Alignment with expected traits (0.20) ---
    if expected_traits:
        should_clarify = expected_traits.get("should_ask_clarification", None)
        if should_clarify is not None and parsed and isinstance(parsed, dict):
            detected = parsed.get("needsClarification", parsed.get("needs_clarification", None))
            if detected is not None:
                if bool(detected) == bool(should_clarify):
                    score += 0.20  # Correct detection
                else:
                    score += 0.05  # Wrong detection, partial credit for structure
            else:
                score += 0.10  # Can't tell, moderate credit
        else:
            score += 0.10  # No expected trait, moderate credit
    else:
        score += 0.10  # No traits to compare against
    
    return min(1.0, round(score, 4))


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


def architect_metric(dataset_item: Dict[str, Any], llm_output: str) -> float:
    """
    Fast, deterministic metric for architect prompt optimization.
    
    Evaluates plan structure quality using heuristic checks (no LLM API calls).
    Works with both JSON output and free-form text plans.
    
    Scores:
    - JSON parseable plan structure                              — 0.25
    - Task count and quality                                     — 0.30
    - Required fields (title, phases, dependencies, subtasks)    — 0.25
    - Content relevance to the original request                  — 0.20
    
    Returns a score from 0.0 to 1.0.
    """
    import re
    
    expected_traits = dataset_item.get("expected_traits", {})
    if isinstance(expected_traits, str):
        try:
            expected_traits = json.loads(expected_traits)
        except (json.JSONDecodeError, TypeError):
            expected_traits = {}
    
    score = 0.0
    output = llm_output.strip() if llm_output else ""
    
    if not output:
        return 0.0
    
    # Try to parse as JSON
    plan = None
    try:
        cleaned = re.sub(r"```(?:json)?\s*", "", output).strip().rstrip("`").strip()
        plan = json.loads(cleaned)
    except (json.JSONDecodeError, TypeError):
        # Try to find a JSON object in the text
        json_match = re.search(r'\{.*\}', output, re.DOTALL)
        if json_match:
            try:
                plan = json.loads(json_match.group())
            except (json.JSONDecodeError, TypeError):
                pass
    
    if plan and isinstance(plan, dict):
        if "plan" in plan:
            plan = plan["plan"]
    
    # --- 1. JSON structure quality (0.25) ---
    if plan and isinstance(plan, dict):
        score += 0.15  # Valid JSON
        tasks = plan.get("tasks", [])
        if isinstance(tasks, list) and len(tasks) > 0:
            score += 0.10  # Has tasks array
    elif output and len(output) > 200:
        # Non-JSON but substantial response
        score += 0.05
    
    # --- 2. Task count and quality (0.30) ---
    tasks = []
    if plan and isinstance(plan, dict):
        tasks = plan.get("tasks", [])
    
    if tasks:
        n_tasks = len(tasks)
        min_tasks = expected_traits.get("min_tasks", 3)
        max_tasks = expected_traits.get("max_tasks", 15)
        
        if min_tasks <= n_tasks <= max_tasks:
            score += 0.15  # Ideal range
        elif n_tasks > 0:
            # Partial credit based on distance from ideal range
            if n_tasks < min_tasks:
                score += 0.08 * (n_tasks / min_tasks)
            else:
                score += 0.08
        
        # Tasks should have names and IDs
        named = sum(1 for t in tasks if t.get("name") or t.get("id"))
        score += 0.15 * (named / max(len(tasks), 1))
    else:
        # No parsed tasks — look for task-like patterns in text
        task_patterns = re.findall(
            r'(?:task|phase|step|milestone)\s*[:\d#]',
            output.lower()
        )
        if len(task_patterns) >= 3:
            score += 0.10
        elif task_patterns:
            score += 0.05
    
    # --- 3. Required fields (0.25) ---
    if plan and isinstance(plan, dict):
        field_checks = [
            bool(plan.get("projectTitle") or plan.get("title") or plan.get("project_title")),
            bool(plan.get("projectSummary") or plan.get("summary") or plan.get("description")),
            any(t.get("phase") for t in tasks) if tasks else False,
            any(t.get("dependencies") for t in tasks) if tasks else False,
            any(t.get("subtasks") for t in tasks) if tasks else False,
        ]
        score += 0.25 * (sum(field_checks) / len(field_checks))
    else:
        # Check for structural keywords in text
        structural_keywords = ["phase", "depend", "subtask", "milestone", "timeline"]
        found = sum(1 for kw in structural_keywords if kw in output.lower())
        score += 0.25 * (found / len(structural_keywords))
    
    # --- 4. Content relevance (0.20) ---
    question = dataset_item.get("question", "").lower()
    topic_words = [w for w in question.split() if len(w) > 3]
    if topic_words:
        mentioned = sum(1 for w in topic_words[:8] if w in output.lower())
        relevance = mentioned / min(len(topic_words), 8)
        score += 0.20 * relevance
    else:
        score += 0.10  # No question to compare
    
    return min(1.0, round(score, 4))


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
