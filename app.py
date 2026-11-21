"""Maplewood Family Clinic patient portal: a 4-agent CrewAI crew answers patient questions.

The crew runs as a subprocess (python main.py "<question>") so CrewAI's verbose stdout
can be streamed into the page while it runs.
LLM settings: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL from env, .env, or Streamlit secrets.
Agent spec cards are read from config/agents.yaml and config/tasks.yaml.
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import streamlit as st
import yaml
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")

URGENCY_BADGE = {"EMERGENCY": ":red-badge[🚨 Emergency]", "URGENT": ":orange-badge[⚠️ Urgent]",
                 "ROUTINE": ":green-badge[✓ Routine]"}
EXAMPLES = ["What are your opening hours on Saturday?",
            "Can I book a flu jab next week?",
            "How do I get a refill for my blood pressure medicine?",
            "How much is a health screening and do I need to fast?"]


def secret(name):
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass  # no secrets.toml (local run)
    return os.getenv(name)


def secrets_problem():
    """Return an error message if LLM settings are missing, else None."""
    missing = [k for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL") if not secret(k)]
    if not missing:
        return None
    # Diagnose without revealing values: missing vs. unparseable vs. key absent.
    try:
        visible = sorted(st.secrets.keys())
        status = (f"Secret names this app can see: {', '.join(visible)}."
                  if visible else "The Secrets box is saved but empty.")
    except Exception as e:
        msg = str(e)
        if "Error parsing" in msg:
            where = re.search(r"line \d+, column \d+", msg)
            status = ("Secrets were saved but are not valid TOML"
                      + (f" (problem at {where.group(0)})" if where else "")
                      + ". Each line must look like NAME = \"value\", with no ``` fences.")
        else:
            status = "No secrets have been saved for this app."
    return (f"LLM settings missing: {', '.join(missing)}, so the assistant is offline.\n\n"
            f"{status}\n\nFix: app menu (⋮) → Settings → Secrets → paste the secrets block → Save.")


def run_crew(question, status):
    """Run main.py, stream its log into the status box, return (triage, reply, log, ok)."""
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "COLUMNS": "100",
           "CREWAI_TRACING_ENABLED": "false", "CREWAI_DISABLE_TELEMETRY": "true",
           "OTEL_SDK_DISABLED": "true"}
    try:  # Streamlit Cloud secrets -> child environment
        env.update({k: str(v) for k, v in st.secrets.items() if k.startswith("LLM_")})
    except Exception:
        pass  # no secrets.toml locally; main.py reads .env instead

    box, lines = status.empty(), []
    proc = subprocess.Popen([sys.executable, "main.py", question], cwd=HERE, env=env,
                            text=True, bufsize=1, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    current = None
    for line in proc.stdout:
        lines.append(line.rstrip("\n"))
        m = re.search(r"Agent:\s+(.+?)\s*│", line)
        if m and m.group(1) != current:
            current = m.group(1)
            status.update(label=f"{current} is working…")
        box.code("\n".join(lines[-60:]), language=None)
    proc.wait()

    log = "\n".join(lines)
    if proc.returncode != 0 or "=== FINAL OUTPUT ===" not in log:
        return "", "", log, False
    triage = log.split("=== TRIAGE ===", 1)[1].split("=== FINAL OUTPUT ===", 1)[0].strip()
    reply = log.split("=== FINAL OUTPUT ===", 1)[1].split("=== TASKS COMPLETED ===", 1)[0].strip()
    return triage, reply, log, True


def error_hint(log):
    """Pull the API error out of a failed run and say which setting to check."""
    err = log.split("=== ERROR ===", 1)[1].strip() if "=== ERROR ===" in log else ""
    if not err:
        codes = re.findall(r"Error code: \d+ - .{0,300}", log)
        err = codes[-1] if codes else "No error message found; see the agent log below."
    low = err.lower()
    if "api key" in low or "401" in low or "403" in low or "unauthori" in low:
        hint = "Check **LLM_API_KEY** in Secrets (and that it belongs to the provider in LLM_BASE_URL)."
    elif "model" in low or "404" in low:
        hint = "Check **LLM_MODEL** in Secrets: just the model name, e.g. `gemini-3.5-flash-lite`."
    elif "429" in low or "quota" in low or "rate" in low:
        hint = "The provider's rate limit or quota was hit. Wait a minute and try again."
    else:
        hint = "Check the three LLM_* values in Secrets."
    return f"**API error:** `{err[:400]}`\n\n{hint}"


def urgency_of(triage):
    m = re.search(r"URGENCY:\s*(EMERGENCY|URGENT|ROUTINE)", triage)
    return m.group(1) if m else None


def show_answer(msg):
    urgency = urgency_of(msg["triage"])
    if urgency == "EMERGENCY":
        st.error("**This may be an emergency. Call 995 or go to the nearest A&E now.** "
                 "Thoughts of suicide or self-harm: call SOS on 1767 (24 hours).")
    if urgency:
        st.markdown(f"Triage: {URGENCY_BADGE[urgency]}")
    if msg["ok"]:
        st.markdown(msg["reply"])
    else:
        st.error("Sorry, the assistant couldn't answer just now. Please call 6123 4567.")
        st.warning(error_hint(msg["log"]))
    with st.expander("Behind the scenes: agent log"):
        st.code(msg["log"], language=None)


# ---------------------------------------------------------------- page
st.set_page_config(page_title="Maplewood Patient Portal", page_icon="🩺")

with st.sidebar:
    st.markdown("## 🩺 Maplewood Family Clinic")
    st.caption("Patient portal · AI assistant")
    st.error("**Emergency?** Call **995** or go to the nearest A&E.\n\n"
             "Thoughts of self-harm: **SOS 1767** (24h).")
    st.markdown("**Opening hours**  \nMon–Fri 8:30–12:30, 2:00–6:00  \nSat 8:30–12:30  \nSun & PH closed")
    st.markdown("**Phone** 6123 4567")
    st.divider()
    st.caption("Demo with a fictional clinic and data. The assistant gives general clinic "
               "information, not medical advice, and cannot confirm bookings.")

st.title("Ask the clinic")
st.caption("Four AI agents work together on your question: triage, clinic info, "
           "appointments, and a safety review before anything reaches you.")

chat_tab, spec_tab = st.tabs(["💬 Ask a question", "🧩 Agent spec cards"])

with chat_tab:
    problem = secrets_problem()
    if problem:
        st.error(problem)
    else:
        if "msgs" not in st.session_state:
            st.session_state.msgs = []

        for msg in st.session_state.msgs:
            with st.chat_message("user"):
                st.markdown(msg["question"])
            with st.chat_message("assistant", avatar="🩺"):
                show_answer(msg)

        clicked = None
        if not st.session_state.msgs:
            st.markdown("**Try asking:**")
            cols = st.columns(2)
            for i, ex in enumerate(EXAMPLES):
                if cols[i % 2].button(ex, use_container_width=True):
                    clicked = ex

        typed = st.chat_input("Ask about appointments, hours, fees, refills…", max_chars=500)
        question = (typed or clicked or "").strip()
        if question:
            with st.chat_message("user"):
                st.markdown(question)
            with st.chat_message("assistant", avatar="🩺"):
                status = st.status("Triage nurse is reading your message…", expanded=False)
                with status:
                    triage, reply, log, ok = run_crew(question, status)
                status.update(label="Agents finished" if ok else "Something went wrong",
                              state="complete" if ok else "error")
            st.session_state.msgs.append(
                {"question": question, "triage": triage, "reply": reply, "log": log, "ok": ok})
            st.rerun()

with spec_tab:
    agents = yaml.safe_load((HERE / "config/agents.yaml").read_text())
    tasks = yaml.safe_load((HERE / "config/tasks.yaml").read_text())
    # Tool descriptions = docstrings in clinic_tools.py, read without importing crewai (slow).
    tree = ast.parse((HERE / "clinic_tools.py").read_text())
    tool_docs = {f.name: " ".join((ast.get_docstring(f) or "").split())
                 for f in tree.body if isinstance(f, ast.FunctionDef)}

    st.caption("Source of truth: `config/agents.yaml` + `config/tasks.yaml` (standard CrewAI "
               "config, loaded by `@CrewBase` in `crew.py`). Agents run top to bottom.")
    for n, (task_name, t) in enumerate(tasks.items(), 1):
        a = agents[t["agent"]]
        with st.container(border=True):
            st.markdown(f"### {n}. {a['role']}")
            st.caption(f"`{t['agent']}` · task `{task_name}`"
                       + (f" · uses output of {', '.join(f'`{c}`' for c in t['context'])}"
                          if t.get("context") else ""))
            st.markdown(f"**a) Role**  \n{a['role']}: {a['backstory'].strip()}")
            st.markdown(f"**b) Objective and inputs**  \n_Goal:_ {a['goal'].strip()}")
            st.markdown(t["description"].strip())
            tools = a.get("tools") or []
            tool_lines = [f"- `{name}`: {tool_docs.get(name, '').split('. ')[0].rstrip('.')}."
                          for name in tools]
            st.markdown("**c) Tools**  \n" + ("\n".join(tool_lines) if tools
                        else "None. Works only from the other agents' results."))
            st.markdown("**d) Output format**")
            st.markdown(t["expected_output"].strip())
            st.markdown(f"**e) Done when**  \n{t['done_when'].strip()}")
