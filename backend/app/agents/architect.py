"""
Architect Agent - Creates structural backbone of project plans.
Uses Google ADK LlmAgent with Google Search for research.
"""

from google.adk.agents import LlmAgent

from ..config import get_settings
from .tools import get_current_date
from .output_schemas import ProjectPlanOutput

settings = get_settings()


def create_architect_agent(critique: str | None = None) -> LlmAgent:
    """
    Create the Architect Agent that designs project structure.
    
    Responsibilities:
    - Research workflows using Google Search
    - Create hierarchical structure (Phases -> Tasks -> Subtasks)
    - Define logical dependencies
    
    Args:
        critique: Optional feedback from Reviewer to incorporate
    """
    critique_section = ""
    if critique:
        critique_section = f"""

**IMPORTANT FEEDBACK FROM REVIEWER (Must Fix):**
Your previous attempt was rejected. Fix the following issues:
{critique}
"""
    
    return LlmAgent(
        name="architect_agent",
        model=settings.pro_model,
        description="Creates structural backbone of project plans with phases, tasks, and subtasks",
        instruction=f"""You are the ARCHITECT Agent.
Goal: Create the STRUCTURAL BACKBONE of a project plan.

Current Date: {get_current_date()}

**Instructions:**
1. **Research & URLs**: Use Google Search to find best practices and workflows.
   If user provided a URL, prioritize researching that resource.

2. **Breakdown**: Create a hierarchical structure:
   - Phases: Major milestones or stages
   - Tasks: Actionable work items within each phase
   - Subtasks: Each Task MUST have at least 3-5 concrete subtasks

3. **Dependencies**: Define logical order (Task B depends on Task A).
   - Use task IDs for dependencies
   - Ensure no circular dependencies
   
4. **Task IDs**: Use descriptive IDs like "phase1_task1", "design_wireframes", etc.

5. **Output**: Return the JSON structure.
   - Set 'duration' to placeholder values (the Estimator Agent will calculate later)
   - Set 'buffer' to 0 (will be calculated later)
   - Set 'startOffset' to 0 (will be calculated later)

Output pure JSON matching the schema.
{critique_section}""",
        output_schema=ProjectPlanOutput,
    )


# Default architect agent without critique
architect_agent = create_architect_agent()
