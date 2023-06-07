"""Tasks manager for Autogpt"""

from autogpt.commands.command import command
from autogpt.tasks_manager import TasksManager


TM = TasksManager()


@command("select_task", "Select next task", '"task_id": "<task_id>"')
def select_task(task_id: str) -> str:
    """select a task to complete
    
    Args:
        task_id (str): task_id of the task to complete

    Returns:
        str: A message indicating success or failure
    """
    return TM.update_task_status(task_id, "WIP")
