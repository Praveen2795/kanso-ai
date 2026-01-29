"""
Scheduling algorithm for task dependency resolution.
Ported from TypeScript recalculateSchedule function.
"""

from ..models import Task


def recalculate_schedule(tasks: list[Task]) -> list[Task]:
    """
    Deterministic scheduler to ensure no overlaps on dependencies.
    Uses topological sort with cycle detection.
    
    Args:
        tasks: List of tasks with dependencies
        
    Returns:
        Tasks with recalculated start_offset values, sorted by start time
    """
    # Create a map for quick lookup
    task_map: dict[str, Task] = {}
    for task in tasks:
        # Clone task with reset start_offset
        task_copy = task.model_copy(deep=True)
        task_copy.start_offset = 0
        task_map[task.id] = task_copy
    
    visited: set[str] = set()
    visiting: set[str] = set()
    
    def calculate_start(task_id: str) -> float:
        """Recursively calculate start offset based on dependencies."""
        # Cycle detection
        if task_id in visiting:
            print(f"Warning: Circular dependency detected: {task_id}")
            return 0
        
        # Already computed
        if task_id in visited:
            return task_map[task_id].start_offset
        
        visiting.add(task_id)
        task = task_map.get(task_id)
        
        max_dependency_end = 0.0
        if task and task.dependencies:
            for dep_id in task.dependencies:
                if dep_id in task_map:
                    dep_start = calculate_start(dep_id)
                    dep_task = task_map[dep_id]
                    dep_end = dep_start + (dep_task.duration or 0) + (dep_task.buffer or 0)
                    if dep_end > max_dependency_end:
                        max_dependency_end = dep_end
        
        if task:
            task.start_offset = max_dependency_end
        
        visiting.discard(task_id)
        visited.add(task_id)
        
        return max_dependency_end
    
    # Calculate start offsets for all tasks
    for task in tasks:
        calculate_start(task.id)
    
    # Return tasks sorted by start offset
    return sorted(task_map.values(), key=lambda t: t.start_offset)


def calculate_total_duration(tasks: list[Task]) -> float:
    """Calculate total project duration based on task end times."""
    if not tasks:
        return 0
    
    max_end = 0.0
    for task in tasks:
        task_end = task.start_offset + task.duration + task.buffer
        if task_end > max_end:
            max_end = task_end
    
    return max_end
