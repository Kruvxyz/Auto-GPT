from autogpt.agent.agent import Agent
from autogpt.commands.command import CommandRegistry
from autogpt.prompts.prompt import DEFAULT_TRIGGERING_PROMPT, construct_task_ai_config
from autogpt.tasks_manager import TasksManager
from autogpt.prompts.generator import PromptGenerator
from autogpt.prompts.prompt import build_default_prompt_generator
from autogpt.config import Config
from autogpt.logs import logger

from colorama import Fore, Style

TM = TasksManager()

class TaskAI:
    def __init__(self) -> None:
        pass

    def create(self, memory, workspace_directory):
        cfg = Config()

        command_registry = CommandRegistry()
        
        command_categories = [
            "autogpt.commands.tasks_manager",
            "autogpt.commands.analyze_code",
            "autogpt.commands.audio_text",
            "autogpt.commands.execute_code",
            "autogpt.commands.file_operations",
            "autogpt.commands.git_operations",
            "autogpt.commands.google_search",
            "autogpt.commands.image_gen",
            "autogpt.commands.improve_code",
            "autogpt.commands.web_selenium",
            "autogpt.commands.write_tests",
            "autogpt.app",
            "autogpt.commands.task_statuses",
        ]
        logger.debug(
            f"The following command categories are disabled: {cfg.disabled_command_categories}"
        )
        command_categories = [
            x for x in command_categories if x not in cfg.disabled_command_categories
        ]

        logger.debug(f"The following command categories are enabled: {command_categories}")

        for command_category in command_categories:
            command_registry.import_commands(command_category)

        ai_config = construct_task_ai_config()
        ai_config.command_registry = command_registry


        # add chat plugins capable of report to logger
        if cfg.chat_messages_enabled:
            for plugin in cfg.plugins:
                if hasattr(plugin, "can_handle_report") and plugin.can_handle_report():
                    logger.info(f"Loaded plugin into logger: {plugin.__class__.__name__}")
                    logger.chat_plugins.append(plugin)
        
        logger.typewriter_log("Using Browser:", Fore.GREEN, cfg.selenium_web_browser)
        system_prompt = ai_config.construct_full_prompt()
        if cfg.debug_mode:
            logger.typewriter_log("Prompt:", Fore.GREEN, system_prompt)

        agent_task = Agent(ai_name="TasksAI", 
                                    memory=memory,
                                    full_message_history=[],
                                    next_action_count=0,
                                    command_registry=command_registry,
                                    config=ai_config,
                                    system_prompt=system_prompt,
                                    triggering_prompt=DEFAULT_TRIGGERING_PROMPT,
                                    workspace_directory=f"{workspace_directory}/TasksAI"
                                    )

        return agent_task
