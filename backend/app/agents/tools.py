"""
Tool definitions for project planning agents.
These are function tools that can be used by ADK agents.
"""

from datetime import datetime
from google.adk.tools import google_search


def get_current_date() -> str:
    """Get the current date formatted for prompts."""
    return datetime.now().strftime("%A, %B %d, %Y")


def format_project_json(project_data: dict) -> str:
    """Format project data as JSON string for prompts."""
    import json
    return json.dumps(project_data, indent=2)


# Export google_search tool for use in agents
__all__ = ["google_search", "get_current_date", "format_project_json"]
