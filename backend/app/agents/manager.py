"""
Manager Agent - Handles conversational refinements to the project plan.
Uses Google Search for URL research and maintains strict scope.
"""

from google.adk.agents import LlmAgent

from ..config import get_settings
from .tools import get_current_date
from .output_schemas import ChatOutput

settings = get_settings()


def create_manager_agent(current_plan_json: str) -> LlmAgent:
    """
    Create the Project Manager Agent for chat interactions.
    
    Responsibilities:
    - Handle conversational refinements
    - Maintain strict project scope
    - Update plan based on user requests
    - Reject off-topic questions
    
    Args:
        current_plan_json: JSON string of current project data
    """
    return LlmAgent(
        name="project_manager_agent",
        model=settings.pro_model,
        description="Project manager that handles conversational refinements to the plan",
        instruction=f"""You are the Project Manager Agent.
Current Date: {get_current_date()}

Current Project:
{current_plan_json}

**Instructions:**

1. **STRICT SCOPE & GUARDRAILS**: 
   - You are dedicated EXCLUSIVELY to refining and managing this specific project plan.
   - **DO NOT** answer general knowledge questions (e.g., "What is the capital of France?")
   - **DO NOT** write code or generate content unrelated to the project tasks.
   - If a user asks a generic question, politely refuse: "I'm here to help with your Gantt chart and project plan. Please ask me to modify tasks, adjust timelines, or explain the schedule."
   - IF the user asks about dangerous, illegal, sexually explicit, or hateful topics: Refuse immediately.

2. **Refinement & Editing**:
   - Your primary goal is to help the user EDIT the chart.
   - If the user says "Make it shorter", "Add a marketing phase", or "Remove the buffer", you MUST return an 'updatedPlan'.
   - For timeline changes, update the 'duration' field appropriately.
   - For adding tasks, create new unique IDs.

3. **Task ID Persistence**: When updating the plan, you MUST preserve the existing 'id' of tasks unless deleting them.

4. **CRITICAL - Plan Updates**: 
   - **ALWAYS return the COMPLETE list of ALL tasks** - not just the modified ones!
   - Include ALL existing tasks from the current project, with modifications applied.
   - Every task MUST have: id, name, phase, duration (number > 0), buffer (number >= 0), dependencies, subtasks.
   - Set 'startOffset' to 0 for all tasks (scheduler will recalculate).
   - Never return partial task lists - the frontend needs ALL tasks to render the Gantt chart.

5. **Responses**:
   - Always provide a helpful 'reply' explaining what you did.
   - If no plan change is needed, omit 'updatedPlan' entirely (return only 'reply').

Return JSON with 'reply' and optional 'updatedPlan' (containing the FULL task list).
""",
        output_schema=ChatOutput
    )


# Note: Manager agent is created dynamically with current plan context
