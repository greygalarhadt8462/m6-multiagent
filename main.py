"""Run the Maplewood patient-portal crew on one patient message.

    python main.py "What time do you open on Saturday?"

LLM settings come from LLM_BASE_URL / LLM_API_KEY / LLM_MODEL: a local .env first,
then the shared course .env at ../ai-agent/.env (values already set are not overridden).
Any OpenAI-compatible endpoint works (OpenRouter, OpenCode Zen, Gemini's OpenAI endpoint).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")
load_dotenv(HERE.parent / "ai-agent" / ".env")

missing = [k for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if not os.getenv(k)]
if missing:
    sys.exit(f"Missing env vars: {', '.join(missing)} (set them in .env)")

from clinic_tools import clinic_today  # noqa: E402
from crew import ClinicPortalCrew  # noqa: E402

if __name__ == "__main__":
    query = " ".join(sys.argv[1:]).strip() or "What are your opening hours on Saturday?"
    try:
        result = ClinicPortalCrew().crew().kickoff(
            inputs={"query": query, "today": clinic_today().strftime("%A %d %B %Y, %H:%M")}
        )
    except Exception as e:  # one readable line for app.py instead of a long traceback
        print("\n=== ERROR ===")
        print(f"{type(e).__name__}: {' '.join(str(e).split())[:600]}")
        sys.exit(1)
    # Markers parsed by app.py
    print("\n=== TRIAGE ===")
    print(result.tasks_output[0].raw)
    print("\n=== FINAL OUTPUT ===")
    print(result.raw)
    print("\n=== TASKS COMPLETED ===")
    for t in result.tasks_output:
        print(f"- {t.agent}: {len(t.raw)} chars")
