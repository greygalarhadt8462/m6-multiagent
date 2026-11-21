"""Maplewood patient-portal crew (crewai==1.15.44), sequential process.

Agents and tasks are defined in config/agents.yaml and config/tasks.yaml (the spec
cards). This class wires them to the LLM and the tools in clinic_tools.py.

  triage_task -> clinic_info_task -> appointment_task -> patient_reply_task
"""

import os

from crewai import Agent, Crew, Process, Task
from crewai.llms.providers.openai.completion import OpenAICompletion
from crewai.project import CrewBase, agent, crew, llm, task, tool

import clinic_tools


class TextToolsLLM(OpenAICompletion):
    """OpenAI-compatible client that makes agents call tools via text (ReAct).

    Gemini 3's OpenAI endpoint rejects native function calls unless a
    'thought_signature' is echoed back, which CrewAI's OpenAI client drops.
    Text-based tool calls work on any OpenAI-compatible endpoint.
    """

    def supports_function_calling(self) -> bool:
        return False


@CrewBase
class ClinicPortalCrew:
    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    # Names referenced from agents.yaml (llm: / tools:)
    @llm
    def portal_llm(self):
        return TextToolsLLM(
            model=os.environ["LLM_MODEL"],
            base_url=os.environ["LLM_BASE_URL"],
            api_key=os.environ["LLM_API_KEY"],
            temperature=0.2,
        )

    @tool
    def red_flag_checker(self):
        return clinic_tools.red_flag_checker

    @tool
    def search_clinic_info(self):
        return clinic_tools.search_clinic_info

    @tool
    def find_open_slots(self):
        return clinic_tools.find_open_slots

    # Agents (one per spec card)
    def _agent(self, name):
        return Agent(config=self.agents_config[name], verbose=True, max_iter=6)

    @agent
    def triage_agent(self) -> Agent:
        return self._agent("triage_agent")

    @agent
    def clinic_info_agent(self) -> Agent:
        return self._agent("clinic_info_agent")

    @agent
    def appointment_agent(self) -> Agent:
        return self._agent("appointment_agent")

    @agent
    def reply_agent(self) -> Agent:
        return self._agent("reply_agent")

    # Tasks, in run order. done_when is a spec-card field CrewAI doesn't know,
    # so it is appended to expected_output, which the agent does see.
    def _task(self, name):
        cfg = dict(self.tasks_config[name])
        done_when = cfg.pop("done_when", "").strip()
        if done_when:
            cfg["expected_output"] = f"{cfg['expected_output'].strip()}\n\nDone when: {done_when}"
        return Task(config=cfg)

    @task
    def triage_task(self) -> Task:
        return self._task("triage_task")

    @task
    def clinic_info_task(self) -> Task:
        return self._task("clinic_info_task")

    @task
    def appointment_task(self) -> Task:
        return self._task("appointment_task")

    @task
    def patient_reply_task(self) -> Task:
        return self._task("patient_reply_task")

    @crew
    def crew(self) -> Crew:
        return Crew(agents=self.agents, tasks=self.tasks, process=Process.sequential, verbose=True)
