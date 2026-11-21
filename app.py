"""Minimal Streamlit page: run the two-agent crew and stream its verbose output live.

The crew runs as a subprocess (python main.py <topic>) so CrewAI's verbose stdout
can be streamed line by line into the page while it runs.
LLM settings: LLM_BASE_URL / LLM_API_KEY / LLM_MODEL from env, .env, or Streamlit secrets.
"""

import hmac
import os
import subprocess
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
load_dotenv(HERE / ".env")


def secret(name):
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass  # no secrets.toml (local run)
    return os.getenv(name)


st.set_page_config(page_title="CrewAI Two-Agent Demo", page_icon="🤖")
st.title("CrewAI two-agent demo")
st.caption("Researcher → Writer, sequential process (crewai 1.15.44)")

# Password gate, fail-closed: with no APP_PASSWORD configured, nobody can run the crew.
expected = secret("APP_PASSWORD")
if not expected:
    try:
        visible = sorted(st.secrets.keys())
    except Exception:
        visible = []
    st.error(
        "APP_PASSWORD is not configured, so running is disabled.\n\n"
        f"Secret names this app can see: {', '.join(visible) or 'none'}.\n\n"
        "Fix: app menu (⋮) → Settings → Secrets → paste the secrets block → Save."
    )
    st.stop()
password = st.text_input("Password", type="password")
authorized = bool(password) and hmac.compare_digest(password.encode(), expected.encode())
if password and not authorized:
    st.warning("Wrong password.")

topic = st.text_input("Topic", "multi-agent systems", max_chars=100)

if st.button("Run crew", type="primary", disabled=not (authorized and topic.strip())):
    env = {**os.environ, "PYTHONUNBUFFERED": "1", "COLUMNS": "100",
           "CREWAI_TRACING_ENABLED": "false", "CREWAI_DISABLE_TELEMETRY": "true",
           "OTEL_SDK_DISABLED": "true"}
    # Streamlit Cloud secrets: copy any LLM_* values into the child's environment.
    try:
        env.update({k: str(v) for k, v in st.secrets.items() if k.startswith("LLM_")})
    except Exception:
        pass  # no secrets.toml locally; main.py reads .env instead

    st.subheader("Verbose output")
    box = st.empty()
    lines = []
    with st.spinner("Crew running…"):
        proc = subprocess.Popen(
            [sys.executable, "main.py", topic.strip()],
            cwd=HERE, env=env, text=True, bufsize=1,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        )
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))
            box.code("\n".join(lines), language=None)
        proc.wait()

    out = "\n".join(lines)
    if proc.returncode == 0 and "=== FINAL OUTPUT ===" in out:
        final = out.split("=== FINAL OUTPUT ===", 1)[1].split("=== TASKS COMPLETED ===", 1)[0]
        st.subheader("Final output")
        st.success(final.strip())
    else:
        st.error(f"Crew failed (exit code {proc.returncode}). See output above.")
