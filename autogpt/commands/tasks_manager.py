"""Tasks manager for Autogpt"""

from autogpt.commands.command import command
from autogpt.config import Config
from autogpt.tasks_manager import TasksManager


CFG = Config()
TM = TasksManager()


@command("add_tasks", "Add a list of tasks", '"tasks": "<list_of_task_descritpions>"')
def create_tasks(tasks: list) -> str:
    """Create tasks
    
    Args:
        tasks (list): list of tasks descriptions 

    Returns:
        str: A message indicating success or failure
    """
    if not TM.is_wip_task_exists():
        return "No current task to add tasks to"
    
    current_task_id = TM.get_wip_task_id()
    if (type(current_task_id)==str):
        return current_task_id

    status = ""
    for task in tasks:
        task_status = TM.add_task(task, task, current_task_id)
        status += f"{task} status: {task_status}\n"

    return status


@command("get_pending_tasks", "Get a list of pending tasks", None)
def get_pending_tasks() -> str:
    """get list of all pending tasks
    
    Args:
        - 

    Returns:
        str: A message with list of pending tasks
    """
    return TM.get_tasks_list("To_do")


# @command("select_task", "Select next task", '"task_id": "<task_id>"', enabled=not CFG.current_task_exists)
# def select_task(task_id: str) -> str:
#     """select a task to complete
    
#     Args:
#         task_id (str): task_id of the task to complete

#     Returns:
#         str: A message indicating success or failure
#     """
#     return TM.update_task_status(task_id, "WIP")


@command("complete_task", "Mark current task completed", None, enabled=True)
def complete_task() -> str:
    """Mark current task as completed
    
    Args:
        -

    Returns:
        str: A message indicating success or failure
    """
    if not TM.is_wip_task_exists():
        return "No current task to complete"
    current_task_id = TM.get_wip_task_id()
    if (type(current_task_id)==str):
        return current_task_id

    return TM.update_task_status(current_task_id, "Done") 


@command("suspend_task", "Suspend current task and return to pending tasks", None, enabled=True)
def suspend_task() -> str:
    """Push current task to pending tasks
    
    Args:
        -

    Returns:
        str: A message indicating success or failure
    """    
    if not TM.is_wip_task_exists():
        return "No current task to suspend"
    current_task_id = TM.get_wip_task_id()
    if (type(current_task_id)==str):
        return current_task_id
    
    return TM.update_task_status(current_task_id, "To_do")
        