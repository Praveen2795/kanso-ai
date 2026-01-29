"""
Analyst Agent - Analyzes user requests and identifies clarification needs.
Uses Google ADK LlmAgent pattern.
"""

from google.adk.agents import LlmAgent

from ..config import get_settings
from .tools import get_current_date
from .output_schemas import ClarificationOutput, FileRelevanceOutput

settings = get_settings()


def create_analyst_agent() -> LlmAgent:
    """
    Create the Analyst Agent that analyzes project requests.
    
    Responsibilities:
    - Verify technical terms using Google Search
    - Check URL accessibility
    - Identify ambiguous requirements
    - Generate clarifying questions
    """
    return LlmAgent(
        name="analyst_agent",
        model=settings.pro_model,
        description="Analyzes project requests to understand scope and identify gaps",
        instruction=f"""You are the ANALYST Agent. Your goal is to deeply understand the user's project request.

Current Date: {get_current_date()}

Your responsibilities:
1. **Verify Technical Terms**: Use Google Search to check if technical terms exist and are correctly used.
2. **Link Detection**: If the user provided a URL, check if it's accessible via Google Search.
3. **Identify Ambiguity**: If context is missing (skill level, deadline, scale), ask for it.

Generate 2-3 **SMART** questions if clarification is needed:
- Specific: Target exact missing information
- Measurable: Can be quantified or clearly answered
- Achievable: Within the user's likely knowledge
- Relevant: Directly impacts project planning
- Time-bound: If deadlines are unclear

Guardrails: Reject illegal, harmful, or inappropriate topics immediately.

If the request is clear and complete, set needsClarification to false.
""",
        output_schema=ClarificationOutput,
    )


def create_file_validator_agent() -> LlmAgent:
    """
    Create an agent that validates file relevance to the project topic.
    Uses a faster model for quick validation.
    """
    return LlmAgent(
        name="file_validator_agent",
        model=settings.default_model,
        description="Validates if uploaded files are relevant to the project",
        instruction="""You are a VALIDATION AGENT.

Task: Determine if the content of the attached file is RELEVANT to the User Topic.

Rules:
1. If the file contains a schedule, list, notes, diagram, or text related to the topic, return isRelevant: true.
2. If the file is completely unrelated (e.g., a selfie, a meme, a receipt) and the topic is something else, return isRelevant: false.
3. If you are unsure or the connection is weak but possible, return isRelevant: true.

Output JSON with isRelevant and reason.
""",
        output_schema=FileRelevanceOutput,
    )


# Pre-instantiate agents for reuse
analyst_agent = create_analyst_agent()
file_validator_agent = create_file_validator_agent()
