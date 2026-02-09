"""
Reviewer Agent - Validates structure and estimates from other agents.
Acts as quality control in the multi-agent pipeline.
Uses iteration loops with max_iterations for controlled validation.
"""

from google.adk.agents import LlmAgent

from ..config import get_settings
from .output_schemas import ValidationOutput

settings = get_settings()

# Maximum iterations for validation loops (prevents endless retries)
MAX_VALIDATION_ITERATIONS = 2


def create_structure_reviewer_agent() -> LlmAgent:
    """
    Create a Reviewer Agent that validates project structure.
    
    Checks:
    - Logical dependencies
    - Missing phases or tasks
    - Subtask specificity
    """
    return LlmAgent(
        name="structure_reviewer_agent",
        model=settings.default_model,
        description="Validates project structure for logical gaps and completeness",
        instruction="""You are the REVIEWER Agent. You are quality control for the Architect.

**Your Checklist:**

1. **Dependencies Logic**: Are the dependencies logical?
   - Example: You can't paint walls before building them
   - Example: You can't deploy before testing
   
2. **Completeness**: Are any essential phases/tasks missing?
   - Software project without Testing phase = INVALID
   - Marketing campaign without Analytics/Measurement = INVALID
   - Event planning without Venue/Logistics = INVALID

3. **Subtask Specificity**: Are subtasks too vague?
   - "Do stuff" = INVALID
   - "Research competitors for 2 hours" = VALID

4. **ID Consistency**: Do dependency IDs reference existing task IDs?

If MAJOR issues exist, set 'isValid' to false and write a DETAILED critique for the Architect to fix it.
Be specific about what's wrong and how to fix it.

If minor or no issues, set 'isValid' to true with a brief acknowledgment.
""",
        output_schema=ValidationOutput
    )


def create_estimate_reviewer_agent() -> LlmAgent:
    """
    Create a Reviewer Agent that validates time estimates.
    
    Checks:
    - Realistic time allocations
    - Buffer inclusion
    - Total timeline sanity
    """
    return LlmAgent(
        name="estimate_reviewer_agent",
        model=settings.default_model,
        description="Validates time estimates for realism and completeness",
        instruction="""You are the REVIEWER Agent. You are quality control for the Estimator.

**Your Checklist:**

1. **Realistic Times**: Are the times realistic?
   - "Build entire backend" = 1 hour is IMPOSSIBLE -> Reject
   - "Write simple script" = 40 hours is EXCESSIVE -> Reject
   - Consider complexity level when judging

2. **Buffers**: Are appropriate buffers included?
   - High complexity tasks need 25-30% buffer
   - No buffer at all = INVALID

3. **Total Timeline**: Is the overall timeline reasonable?
   - A 2-week project taking 1000 hours = INVALID
   - Consider working hours per day (assume 6-8 productive hours)

4. **Subtask Aggregation**: Does parent duration roughly equal sum of subtasks?

If MAJOR issues exist, set 'isValid' to false and write a DETAILED critique for the Estimator.

If estimates look reasonable, set 'isValid' to true.
""",
        output_schema=ValidationOutput
    )


def create_final_reviewer_agent() -> LlmAgent:
    """
    Create a Final Reviewer that sanitizes and formats the output.
    This is the last pass before sending to frontend.
    """
    from .output_schemas import ProjectPlanOutput
    
    return LlmAgent(
        name="final_reviewer_agent",
        model=settings.default_model,
        description="Final cleanup and formatting of project plan",
        instruction="""You are the FINAL REVIEWER.
Ensure this JSON is perfectly formatted for the frontend.

**Sanity Checks:**
- Ensure 'duration' is > 0 for all tasks
- Ensure 'dependencies' refer to real task IDs that exist
- Ensure all required fields are present
- Clean up any formatting issues

Return the cleaned JSON. Do not add or remove tasks, just ensure data integrity.
""",
        output_schema=ProjectPlanOutput
    )


# Pre-instantiate reviewer agents
structure_reviewer = create_structure_reviewer_agent()
estimate_reviewer = create_estimate_reviewer_agent()
final_reviewer = create_final_reviewer_agent()
