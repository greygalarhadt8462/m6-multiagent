"""Minimal two-agent CrewAI crew (crewai==1.15.44), sequential process.

Researcher -> Writer. The writer's task receives the researcher's output as context.

LLM settings come from LLM_BASE_URL / LLM_API_KEY / LLM_MODEL: a local .env first,
then the shared course .env at ../ai-agent/.env (values already set are not overridden).
Any OpenAI-compatible endpoint works (OpenRouter, OpenCode Zen, Gemini's OpenAI endpoint).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from crewai import LLM, Agent, Crew, Process, Task

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
load_dotenv(HERE.parent / "ai-agent" / ".env")

missing = [k for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if not os.getenv(k)]
if missing:
    sys.exit(f"Missing env vars: {', '.join(missing)} (set them in .env)")

# "openai/<model>" + base_url routes through CrewAI's native OpenAI-compatible client.
llm = LLM(
    model=f"openai/{os.environ['LLM_MODEL']}",
    base_url=os.environ["LLM_BASE_URL"],
    api_key=os.environ["LLM_API_KEY"],
    temperature=0.3,
)

researcher = Agent(
    role="Researcher",
    goal="Collect three accurate, concise facts about {topic}",
    backstory="A careful analyst who prefers short, verifiable statements.",
    llm=llm,
    verbose=True,
)

writer = Agent(
    role="Writer",
    goal="Turn research notes about {topic} into a short, clear paragraph",
    backstory="A technical writer who explains things plainly.",
    llm=llm,
    verbose=True,
)

research_task = Task(
    description="List exactly three key facts about {topic}. One line each.",
    expected_output="A numbered list of three facts.",
    agent=researcher,
)

write_task = Task(
    description="Using the researcher's facts, write one paragraph (under 80 words) about {topic}.",
    expected_output="A single paragraph under 80 words.",
    agent=writer,
    context=[research_task],
)

crew = Crew(
    agents=[researcher, writer],
    tasks=[research_task, write_task],
    process=Process.sequential,
    verbose=True,
)

if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "multi-agent systems"
    result = crew.kickoff(inputs={"topic": topic})
    print("\n=== FINAL OUTPUT ===")
    print(result.raw)
    print("\n=== TASKS COMPLETED ===")
    for t in result.tasks_output:
        print(f"- {t.agent}: {len(t.raw)} chars")
