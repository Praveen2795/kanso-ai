"""
Calendar export functionality for generating ICS files.
Supports Google Calendar, Outlook, Apple Calendar, and other iCalendar-compatible apps.
"""

from datetime import datetime, timedelta
from typing import Optional
from uuid import uuid4

from .models import ProjectData, Task


def generate_ics(
    project: ProjectData,
    start_date: Optional[datetime] = None,
    hours_per_day: float = 8.0,
    working_days: list[int] = None
) -> str:
    """
    Generate an ICS (iCalendar) file from project data.
    
    Args:
        project: The project data with tasks
        start_date: When to start the project (defaults to tomorrow)
        hours_per_day: Working hours per day (default 8)
        working_days: List of weekday indices (0=Monday, 6=Sunday). 
                      Defaults to Mon-Fri [0,1,2,3,4]
    
    Returns:
        ICS file content as string
    """
    if start_date is None:
        # Default to tomorrow at 9 AM
        start_date = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
        start_date += timedelta(days=1)
    
    if working_days is None:
        working_days = [0, 1, 2, 3, 4]  # Monday to Friday
    
    # ICS header
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Kanso.AI//Project Planner//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{escape_ics_text(project.title)}",
        f"X-WR-CALDESC:{escape_ics_text(project.description)}",
    ]
    
    # Calculate events for each task
    for task in project.tasks:
        events = create_task_events(
            task=task,
            project_start=start_date,
            hours_per_day=hours_per_day,
            working_days=working_days
        )
        lines.extend(events)
    
    # Add a project summary event
    total_days = calculate_working_days(project.total_duration, hours_per_day)
    project_end = add_working_days(start_date, total_days, working_days, hours_per_day)
    
    lines.extend([
        "BEGIN:VEVENT",
        f"UID:{uuid4()}@kanso.ai",
        f"DTSTAMP:{format_datetime(datetime.now())}",
        f"DTSTART;VALUE=DATE:{start_date.strftime('%Y%m%d')}",
        f"DTEND;VALUE=DATE:{project_end.strftime('%Y%m%d')}",
        f"SUMMARY:📊 {escape_ics_text(project.title)}",
        f"DESCRIPTION:{escape_ics_text(create_project_description(project))}",
        "TRANSP:TRANSPARENT",  # Don't block time for the overall project
        "END:VEVENT",
    ])
    
    lines.append("END:VCALENDAR")
    
    return "\r\n".join(lines)


def create_task_events(
    task: Task,
    project_start: datetime,
    hours_per_day: float,
    working_days: list[int]
) -> list[str]:
    """Create ICS events for a task and its subtasks."""
    events = []
    
    # Calculate task start time based on offset
    task_start = add_working_hours(
        project_start, 
        task.start_offset, 
        hours_per_day, 
        working_days
    )
    
    # Main task event
    task_duration_hours = task.duration + task.buffer
    task_end = add_working_hours(
        task_start,
        task_duration_hours,
        hours_per_day,
        working_days
    )
    
    # Build description with subtasks
    description_parts = []
    if task.description:
        description_parts.append(task.description)
    
    description_parts.append(f"\\n\\n📋 Phase: {task.phase}")
    description_parts.append(f"⏱️ Duration: {task.duration:.1f}h")
    if task.buffer > 0:
        description_parts.append(f"🛡️ Buffer: {task.buffer:.1f}h")
    description_parts.append(f"📊 Complexity: {task.complexity}")
    
    if task.subtasks:
        description_parts.append("\\n\\n📝 Subtasks:")
        for i, st in enumerate(task.subtasks, 1):
            subtask_line = f"  {i}. {st.name} ({st.duration:.1f}h)"
            if st.description:
                subtask_line += f" - {st.description}"
            description_parts.append(subtask_line)
    
    description = "\\n".join(description_parts)
    
    # Get phase emoji based on common keywords
    phase_emoji = get_phase_emoji(task.phase)
    
    events.extend([
        "BEGIN:VEVENT",
        f"UID:{uuid4()}@kanso.ai",
        f"DTSTAMP:{format_datetime(datetime.now())}",
        f"DTSTART:{format_datetime(task_start)}",
        f"DTEND:{format_datetime(task_end)}",
        f"SUMMARY:{phase_emoji} {escape_ics_text(task.name)}",
        f"DESCRIPTION:{escape_ics_text(description)}",
        f"CATEGORIES:{escape_ics_text(task.phase)}",
        "STATUS:CONFIRMED",
        "TRANSP:OPAQUE",  # Block time for tasks
        "END:VEVENT",
    ])
    
    return events


def add_working_hours(
    start: datetime,
    hours: float,
    hours_per_day: float,
    working_days: list[int]
) -> datetime:
    """Add working hours to a datetime, respecting working days."""
    current = start
    remaining_hours = hours
    
    while remaining_hours > 0:
        # Check if current day is a working day
        if current.weekday() in working_days:
            # Calculate hours left in current day
            day_start_hour = 9  # 9 AM start
            day_end_hour = day_start_hour + hours_per_day
            
            if current.hour < day_start_hour:
                current = current.replace(hour=day_start_hour, minute=0)
            
            hours_left_today = max(0, day_end_hour - current.hour - current.minute / 60)
            
            if remaining_hours <= hours_left_today:
                # Task fits in current day
                current += timedelta(hours=remaining_hours)
                remaining_hours = 0
            else:
                # Use remaining hours today and continue tomorrow
                remaining_hours -= hours_left_today
                current = (current + timedelta(days=1)).replace(hour=9, minute=0)
        else:
            # Skip non-working day
            current = (current + timedelta(days=1)).replace(hour=9, minute=0)
    
    return current


def add_working_days(
    start: datetime,
    days: float,
    working_days: list[int],
    hours_per_day: float
) -> datetime:
    """Add working days to a date."""
    return add_working_hours(start, days * hours_per_day, hours_per_day, working_days)


def calculate_working_days(total_hours: float, hours_per_day: float) -> float:
    """Calculate number of working days from total hours."""
    return total_hours / hours_per_day if hours_per_day > 0 else 0


def format_datetime(dt: datetime) -> str:
    """Format datetime for ICS (UTC format)."""
    return dt.strftime("%Y%m%dT%H%M%SZ")


def escape_ics_text(text: str) -> str:
    """Escape special characters for ICS format."""
    if not text:
        return ""
    # ICS requires escaping of commas, semicolons, and backslashes
    text = text.replace("\\", "\\\\")
    text = text.replace(",", "\\,")
    text = text.replace(";", "\\;")
    text = text.replace("\n", "\\n")
    return text


def get_phase_emoji(phase: str) -> str:
    """Get an appropriate emoji for a phase name."""
    phase_lower = phase.lower()
    
    emoji_map = {
        "planning": "📋",
        "research": "🔍",
        "design": "🎨",
        "development": "💻",
        "coding": "💻",
        "testing": "🧪",
        "review": "👀",
        "deployment": "🚀",
        "launch": "🚀",
        "marketing": "📢",
        "documentation": "📄",
        "setup": "⚙️",
        "preparation": "📦",
        "execution": "▶️",
        "completion": "✅",
        "finalization": "🏁",
        "ceremony": "🎉",
        "celebration": "🎊",
        "travel": "✈️",
        "booking": "📅",
        "shopping": "🛒",
        "meeting": "👥",
        "training": "📚",
        "learning": "📚",
    }
    
    for keyword, emoji in emoji_map.items():
        if keyword in phase_lower:
            return emoji
    
    return "📌"  # Default emoji


def create_project_description(project: ProjectData) -> str:
    """Create a summary description for the project event."""
    lines = [
        f"Project: {project.title}",
        "",
        project.description or "No description provided.",
        "",
        f"Total Duration: {project.total_duration:.1f} hours",
        f"Total Tasks: {len(project.tasks)}",
    ]
    
    if project.assumptions:
        lines.append("")
        lines.append("Assumptions:")
        for assumption in project.assumptions:
            lines.append(f"• {assumption}")
    
    lines.append("")
    lines.append("Generated by Kanso.AI")
    
    return "\\n".join(lines)
