from autogpt.agent.agent import Agent
from autogpt.commands.command import CommandRegistry
from autogpt.prompts.prompt import construct_specific_ai_config
from autogpt.tasks_manager import TasksManager
from autogpt.prompts.generator import PromptGenerator
# from autogpt.prompts.prompt import build_default_prompt_generator

TM = TasksManager()

class DecisionAI:
    def __init__(self) -> None:
        pass

    def create(self, memory, workspace_directory):
        command_registry = CommandRegistry()
        # command_registry.import_commands("autogpt.commands.tasks_manager_choose")
        ai_config = construct_specific_ai_config(ai_settings_file="ai_settings_decision")
        # ai_config.command_registry = command_registry

        prompt_generator = PromptGenerator()
        
        # Add constraints to the PromptGenerator object
        prompt_generator.add_constraint(
            "~4000 word limit for short term memory. Your short term memory is short, so"
            " immediately save important information to files."
        )
        prompt_generator.add_constraint(
            "If you are unsure how you previously did something or want to recall past"
            " events, thinking about similar events will help you remember."
        )
        prompt_generator.add_constraint("No user assistance")
        prompt_generator.add_constraint(
            'Exclusively use the commands listed in double quotes e.g. "command name"'
        )

        prompt_generator.add_command("execute", "Execute the command ", None)
        prompt_generator.add_command("evaluate", "Command will not be executed and another command will be choosen", None)

        prompt_generator.goals = ai_config.ai_goals
        prompt_generator.name = ai_config.ai_name
        prompt_generator.role = ai_config.ai_role
        # prompt_generator.command_registry = command_registry

        system_prompt = ai_config.construct_full_prompt(prompt_generator)

        decision_agent = Agent(ai_name="DecisionAI", 
                                    memory=memory,
                                    full_message_history=[],
                                    next_action_count=0,
                                    command_registry=command_registry,
                                    config=ai_config,
                                    system_prompt=system_prompt,
                                    triggering_prompt=f"DecisionAI TRIGGERING PROMPT",
                                    workspace_directory=f"{workspace_directory}/DecisionAI"
                                    )

        return decision_agent
