from datetime import datetime

from colorama import Fore, Style

from autogpt.agent.agent import Agent
from autogpt.agent.instantiations.TasksChooserAI import TasksChooserAI
from autogpt.agent.instantiations.TaskAI import TaskAI
from autogpt.agent.instantiations.DecisionAI import DecisionAI

from autogpt.app import execute_command, get_command
from autogpt.commands.command import CommandRegistry
from autogpt.config import Config
from autogpt.json_utils.json_fix_llm import fix_json_using_multiple_techniques
from autogpt.json_utils.utilities import LLM_DEFAULT_RESPONSE_FORMAT, validate_json
from autogpt.llm import chat_with_ai, create_chat_completion, create_chat_message
from autogpt.llm.token_counter import count_string_tokens
from autogpt.log_cycle.log_cycle import (
    FULL_MESSAGE_HISTORY_FILE_NAME,
    NEXT_ACTION_FILE_NAME,
    USER_INPUT_FILE_NAME,
    LogCycleHandler,
)
from autogpt.logs import logger, print_assistant_thoughts
from autogpt.speech import say_text
from autogpt.spinner import Spinner
from autogpt.utils import clean_input
from autogpt.workspace import Workspace
from autogpt.tasks_manager import TasksManager


class MainLoop:
    """MainLoop class for pulling manage tasks and interact with LLM.

    Attributes: 
        memory: The memory object to use.
        next_action_count: The number of actions to execute.
        workspace_directory: Root directory for workspace.
    """

    def __init__(
        self,
        memory,
        next_action_count,
        workspace_directory,
    ):
        cfg = Config()
        self.memory = memory
        self.summary_memory = (
            "I was created."  # Initial memory necessary to avoid hallucination
        )
        self.last_memory_index = 0
        self.next_action_count = next_action_count
        self.workspace = workspace_directory
        self.created_at = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.cycle_count = 0
        self.log_cycle_handler = LogCycleHandler()

        self.decision_agent = DecisionAI().create(self.memory, self.workspace)
        self.task_agent = None

    def choose_task_step(self):
        cfg = Config()

        agent_choose_task = TasksChooserAI().create(self.memory, self.workspace)
        with Spinner("Selecting a new task... "):
            assistant_reply = chat_with_ai(
                agent_choose_task,
                agent_choose_task.system_prompt,
                agent_choose_task.triggering_prompt,
                agent_choose_task.full_message_history,
                agent_choose_task.memory,
                cfg.fast_token_limit,
            )                
        command_name, arguments, assistant_reply_json = self.parse_assistant_reply(agent_choose_task, assistant_reply)
        try:
            self.execute(agent_choose_task, command_name, arguments)
        except:
            command_name = "self_feedback"
            thoughts = assistant_reply_json.get("thoughts", {})
            arguments = self.get_self_feedback(
                agent_choose_task, thoughts, cfg.fast_llm_model
            )
            self.execute(agent_choose_task, command_name, arguments)

    def main_flow_step(self):
        cfg = Config()
        TM = TasksManager()

        with Spinner("Thinking... "):
            assistant_reply = chat_with_ai(
                self.task_agent,
                self.task_agent.system_prompt,
                self.task_agent.triggering_prompt,
                self.task_agent.full_message_history,
                self.task_agent.memory,
                cfg.fast_token_limit,
            )

        command_name, arguments, assistant_reply_json = self.parse_assistant_reply(self.task_agent, assistant_reply)

        current_task_id = TM.get_wip_task_id()
        current_taks_content = TM.get_task_content(current_task_id)

        # Ugly work to get list of available command 
        #FIXME(guyhod): make this less ugly
        from autogpt.prompts.prompt import build_default_prompt_generator

        prompt_generator = build_default_prompt_generator()
        prompt_generator.command_registry = self.task_agent.command_registry
        for plugin in cfg.plugins:
            if not plugin.can_handle_post_prompt():
                continue
            prompt_generator = plugin.post_prompt(prompt_generator)
            # "Commands:\n"
            # f"{prompt_generator._generate_numbered_list(self.commands, item_type='command')}\n\n"

        reviewer_prompt = f"""Current task details: {current_taks_content}
        List of allowed command: {prompt_generator._generate_numbered_list(prompt_generator.commands, item_type='command')}
        
        Command to execute: '{command_name}' with arguments: '{arguments}'
        """

        with Spinner("Evaluating command... "):
            assistant_reply = chat_with_ai(
                self.decision_agent,
                self.decision_agent.system_prompt,
                reviewer_prompt,
                self.decision_agent.full_message_history,
                self.decision_agent.memory,
                cfg.fast_token_limit,
            )
        decision_name, _, _ = self.parse_assistant_reply(self.decision_agent, assistant_reply)
        print("--------------------------------------")
        print(f"------DecisionAI: {decision_name} ------------")
        print("--------------------------------------")
        if 'evaluate' in decision_name:
            command_name = "self_feedback"
            thoughts = assistant_reply_json.get("thoughts", {})
            arguments = self.get_self_feedback(
                self.task_agent, thoughts, cfg.fast_llm_model
            )
            self.execute(self.task_agent, command_name, arguments)
        else:
            self.execute(self.task_agent, command_name, arguments)

    def start_interaction_loop(self):
        # Interaction Loop
        TM = TasksManager()
        cfg = Config()
        self.cycle_count = 0
        command_name = None
        arguments = None
        current_task = None

        while True:
            while not TM.is_wip_task_exists():
                self.choose_task_step()

            next_task = TM.get_wip_task_id()
            if current_task != next_task:
                print("-----------------------------")
                print(f"----- set task {next_task} --------")
                print("-----------------------------")
                current_task = next_task
                self.task_agent = TaskAI().create(self.memory, self.workspace)

            while TM.is_wip_task_exists():
                self.main_flow_step()

    def _resolve_pathlike_command_args(self, command_args):
        cfg = Config()
        if "directory" in command_args and command_args["directory"] in {"", "/"}:
            workspace = Workspace(self.workspace.root, cfg.restrict_to_workspace)
            command_args["directory"] = str(workspace.root)
        else:
            for pathlike in ["filename", "directory", "clone_path"]:
                if pathlike in command_args:
                    command_args[pathlike] = str(
                        workspace.get_path(command_args[pathlike])
                    )
        return command_args

    def get_self_feedback(self, agent, thoughts: dict, llm_model: str) -> str:
        """Generates a feedback response based on the provided thoughts dictionary.
        This method takes in a dictionary of thoughts containing keys such as 'reasoning',
        'plan', 'thoughts', and 'criticism'. It combines these elements into a single
        feedback message and uses the create_chat_completion() function to generate a
        response based on the input message.
        Args:
            thoughts (dict): A dictionary containing thought elements like reasoning,
            plan, thoughts, and criticism.
        Returns:
            str: A feedback response generated using the provided thoughts dictionary.
        """
        ai_role = agent.config.ai_role

        feedback_prompt = f"Below is a message from me, an AI Agent, assuming the role of {ai_role}. whilst keeping knowledge of my slight limitations as an AI Agent Please evaluate my thought process, reasoning, and plan, and provide a concise paragraph outlining potential improvements. Consider adding or removing ideas that do not align with my role and explaining why, prioritizing thoughts based on their significance, or simply refining my overall thought process."
        reasoning = thoughts.get("reasoning", "")
        plan = thoughts.get("plan", "")
        thought = thoughts.get("thoughts", "")
        feedback_thoughts = thought + reasoning + plan
        return create_chat_completion(
            [{"role": "user", "content": feedback_prompt + feedback_thoughts}],
            llm_model,
        )

    def parse_assistant_reply(self, agent, assistant_reply):
        cfg = Config()
        
        # Parse reply
        assistant_reply_json = fix_json_using_multiple_techniques(assistant_reply)
        for plugin in cfg.plugins:
            if not plugin.can_handle_post_planning():
                continue
            assistant_reply_json = plugin.post_planning(assistant_reply_json)

        # Print Assistant thoughts
        if assistant_reply_json != {}:
            validate_json(assistant_reply_json, LLM_DEFAULT_RESPONSE_FORMAT)
            # Get command name and arguments
            try:
                print_assistant_thoughts(
                    agent.ai_name, assistant_reply_json, cfg.speak_mode
                )
                command_name, arguments = get_command(assistant_reply_json)
                if cfg.speak_mode:
                    say_text(f"I want to execute {command_name}")

                arguments = agent._resolve_pathlike_command_args(arguments)

            except Exception as e:
                logger.error("Error: \n", str(e))
        self.log_cycle_handler.log_cycle(
            agent.config.ai_name,
            agent.created_at,
            agent.cycle_count,
            assistant_reply_json,
            NEXT_ACTION_FILE_NAME,
        )

        logger.typewriter_log(
            "NEXT ACTION: ",
            Fore.CYAN,
            f"COMMAND = {Fore.CYAN}{command_name}{Style.RESET_ALL}  "
            f"ARGUMENTS = {Fore.CYAN}{arguments}{Style.RESET_ALL}",
        )

        return command_name, arguments, assistant_reply_json

    def execute(self, agent, command_name=None, arguments=None):
        cfg = Config()
        result=None

        # Execute command
        if command_name is not None and command_name.lower().startswith("error"):
            result = (
                f"Command {command_name} threw the following error: {arguments}"
            )
        elif command_name == "self_feedback":
            result = f"Self feedback: {arguments}"
        else:
            for plugin in cfg.plugins:
                if not plugin.can_handle_pre_command():
                    continue
                command_name, arguments = plugin.pre_command(
                    command_name, arguments
                )
            command_result = execute_command(
                agent.command_registry,
                command_name,
                arguments,
                agent.config.prompt_generator,
            )
            result = f"Command {command_name} returned: " f"{command_result}"

            result_tlength = count_string_tokens(
                str(command_result), cfg.fast_llm_model
            )
            memory_tlength = count_string_tokens(
                str(agent.summary_memory), cfg.fast_llm_model
            )
            if result_tlength + memory_tlength + 600 > cfg.fast_token_limit:
                result = f"Failure: command {command_name} returned too much output. \
                    Do not execute this command again with the same arguments."

            for plugin in cfg.plugins:
                if not plugin.can_handle_post_command():
                    continue
                result = plugin.post_command(command_name, result)
            if agent.next_action_count > 0:
                agent.next_action_count -= 1

        # Check if there's a result from the command append it to the message
        # history
        if result is not None:
            agent.full_message_history.append(create_chat_message("system", result))
            logger.typewriter_log("SYSTEM: ", Fore.YELLOW, result)
        else:
            agent.full_message_history.append(
                create_chat_message("system", "Unable to execute command")
            )
            logger.typewriter_log(
                "SYSTEM: ", Fore.YELLOW, "Unable to execute command"
            )
