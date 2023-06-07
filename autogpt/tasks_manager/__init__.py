from autogpt.config import Config
import requests


CFG = Config()


class TasksManager(): #FIXME(guyhod): add unit test
    def __init__(self):
        pass

    def is_wip_task_exists(self) -> bool:
        current_task_exists = False
        r = requests.post(f"{CFG.tasks_manager_server}/get_tasks/WIP")
        if r.status_code == 200:
            try: 
                id = r.json()[0].get("id")
                if id:
                    current_task_exists = True
            except:
                current_task_exists = False

        return current_task_exists
        

    def get_wip_task_id(self) -> int:
        r = requests.post(f"{CFG.tasks_manager_server}/get_tasks/WIP")
        if r.status_code == 200:
            try:
                return r.json()[0].get("id")
            except Exception as err:
                return f"Error: {err}"
        else:
            return f"Error: can't get current task id"

    def update_task_activity(self, task_id: int, activity: str) -> bool:
        r = requests.post(f"{CFG.tasks_manager_server}/update_task_activity/{str(task_id)}", json = {
            "activity": activity
        })
        if r.status_code == 200 and r.json().get("status")=="ok":
            return True
        else:
            return False

    def update_task_status(self, task_id: int, next_status: str) -> str:
        r = requests.post(f"{CFG.tasks_manager_server}/update_task_status/{task_id}", json={"status": next_status})
        if r.status_code == 200:
            self.update_task_activity(task_id, f"task status is now {next_status}")
            return "Task was completed successfully."
        
        return f"Error: fail to complte task"
    
    def add_task(self, name: str, description:str, parent: int) -> str:
        r = requests.post(f"{CFG.tasks_manager_server}/add_task", json={"name": name, "description": description})
        status_parent = False
        status_activity = False
        task_id = r.json().get("task_id", 0)

        if r.status_code == 200 and task_id > 0:            
            while not status_parent and not status_activity:
                if not status_parent:
                    r = requests.post(f"{CFG.tasks_manager_server}/update_task_add_son/{parent}", json={"add_son": task_id})
                    if r.json().get("status")=="ok":
                        status_parent = True

                if not status_activity:
                    status_activity = self.update_task_activity(parent, f"Task {name} was added to tasks list")
        
        else:
            return "Task was not added"
        
        return "Task was added successfully."


    def get_tasks_list(self, bucket:str):
        r = requests.post(f"{CFG.tasks_manager_server}/get_tasks/{bucket}")
        tasks_list = "Pending tasks list:"
        if r.status_code == 200:
            tasks = r.json()
            print(tasks)
            for task_json in tasks:
                print(task_json)
                print(str(task_json.get('task_id', 'FAIL')))
                tasks_list += f"\n---------Task {str(task_json.get('task_id', 'FAIL'))}:"
                tasks_list += f"{self.task_decoder(task_json)}\n"

        return tasks_list
    
    def get_task_content(self, task_id: int):
        r = requests.post(f"{CFG.tasks_manager_server}/get_task/{str(task_id)}", json = {})
        if r.status_code == 200 and r.json().get("status", "")!="error":
            return r.json()
        else:
            return False
    
    def task_decoder(self, task_json) -> str:
        if task_json:

            
            sons = []
            son_ids = task_json.get("sons", [])
            for son_id in son_ids:
                sons.append(self.get_task_content(son_id).get("name", "None"))
            return_string = f"""
            task id: '{task_json.get("task_id", "None")}' \n
            task name: '{task_json.get("name", "None")}' \n
            task description: '{task_json.get("description", "None")}' \n
            """
            try:
                parent_id = task_json.get("parent")[0]
                parent = self.get_task_content(parent_id)
                return_string += f"""
            task parent: '{parent.get("name", "None")}' \n
                """
            except:
                pass

            return_string += f"""
            task sub-tasks: '{sons}' \n
            task activities: {task_json.get("activities")} \n

            """

            return return_string

        return ""
    # def get_task_content(task_id: int): #FIXME(guyhod): test this function
    #     r = requests.post(f"{CFG.tasks_manager_server}/get_task/{str(task_id)}", json = {})
    #     if r.status_code == 200 and r.json().get("status", "")!="error":
    #         return r.json()
    #     else:
    #         return False


    # def read_task(task_id: int) -> str:
    #     task_data = get_task_content(task_id)
    #     if task_data:
    #         return f""" 
    #         task name: {task_data["name"]}
    #         task description: {task_data["description"]}
    #           FIXME(guyhod) : complete this function
    #         """
    #     return f"failed to read task {str(task_id)}"
