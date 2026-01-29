"""
Estimator Agent - Calculates time estimates for tasks and subtasks.
Uses bottom-up estimation methodology.
"""

from google.adk.agents import LlmAgent

from ..config import get_settings
from .tools import get_current_date
from .output_schemas import ProjectPlanOutput

settings = get_settings()


def create_estimator_agent(critique: str | None = None) -> LlmAgent:
    """
    Create the Estimator Agent that calculates time estimates.
    
    Responsibilities:
    - Perform bottom-up estimation on subtasks
    - Aggregate subtask durations to parent tasks
    - Add appropriate buffers (20% rule)
    
    Args:
        critique: Optional feedback from Reviewer to incorporate
    """
    critique_section = ""
    if critique:
        critique_section = f"""

**IMPORTANT FEEDBACK FROM REVIEWER (Must Fix):**
Your previous estimates were rejected. Fix the following:
{critique}
"""
    
    return LlmAgent(
        name="estimator_agent",
        model=settings.pro_model,
        description="Calculates realistic time estimates using bottom-up estimation",
        instruction=f"""You are the ESTIMATOR Agent.
Current Date: {get_current_date()}

**Your Goal: Perform a Bottom-Up Estimation**

1. **Iterate through every single task.**

2. **Iterate through every subtask** within that task.

3. **Estimate Duration**: Assign a realistic duration (in hours) to EACH subtask.
   - Consider the 'complexity' level (Low: 1-4h, Medium: 4-8h, High: 8-24h)
   - Be conservative - things take longer than expected
   - Account for context switching and overhead

4. **Aggregation**: The 'duration' for the parent Task MUST be the sum of its subtasks.

5. **Buffers**: Add a 'buffer' (approximately 20% of total duration) to the parent task.
   - High complexity: 25-30% buffer
   - Medium complexity: 20% buffer
   - Low complexity: 10-15% buffer

6. **Start Offsets**: Set startOffset to 0 (the scheduler will calculate based on dependencies).

Return the fully updated JSON with all numbers filled in.
{critique_section}""",
        output_schema=ProjectPlanOutput
    )


# Default estimator agent without critique
estimator_agent = create_estimator_agent()
