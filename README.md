# Maplewood patient portal: multi-agent clinic assistant

A Streamlit patient portal for a fictional family clinic. Patient questions are answered by a
four-agent CrewAI crew (crewai 1.15.44, sequential):

1. **Triage Nurse**: flags emergencies and routes the question (`red_flag_checker`)
2. **Clinic Info Specialist**: looks up hours, fees, services and policies (`search_clinic_info`)
3. **Appointment Coordinator**: offers open slots, never confirms bookings (`find_open_slots`)
4. **Reply & Safety Reviewer**: writes the patient reply and enforces the safety rules

- Workflow diagram: [docs/workflow.md](docs/workflow.md)
- Agent spec cards: [config/agents.yaml](config/agents.yaml) + [config/tasks.yaml](config/tasks.yaml)
  (standard CrewAI YAML config, also shown in the app's **Agent spec cards** tab)

## Run locally

```bash
cp .env.example .env   # fill in LLM_BASE_URL, LLM_API_KEY, LLM_MODEL
uv sync
uv run python main.py "Can I book a flu jab next week?"
uv run streamlit run app.py
```

## Deploy (Streamlit Community Cloud)

Main file `app.py`, Python 3.12, and these secrets:

```toml
LLM_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
LLM_API_KEY = "your-key"
LLM_MODEL = "gemini-3.5-flash-lite"
```

All clinic data is fictional. The assistant gives general clinic information, not medical advice.
