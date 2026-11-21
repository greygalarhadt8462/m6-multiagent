"""Tools the clinic agents can call. All read local, fictional data in ./data.

- red_flag_checker   -> Triage Nurse
- search_clinic_info -> Clinic Information Specialist
- find_open_slots    -> Appointment Coordinator
"""

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from crewai.tools import tool

DATA = Path(__file__).resolve().parent / "data"
SGT = timezone(timedelta(hours=8))  # clinic time; avoids a tzdata dependency


def clinic_today() -> datetime:
    return datetime.now(SGT)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().replace("’", "'"))


@tool("Red Flag Checker")
def red_flag_checker(message: str) -> str:
    """Screen the patient's exact message for emergency or urgent warning signs.
    Pass the full patient message. Returns the matched categories and the
    suggested urgency level (EMERGENCY, URGENT or ROUTINE)."""
    flags = json.loads((DATA / "red_flags.json").read_text())
    text = _norm(message)
    hits = {}
    for level in ("EMERGENCY", "URGENT"):
        for category, phrases in flags[level].items():
            found = [p for p in phrases if p in text]
            if found:
                hits.setdefault(level, []).append(f"{category} (matched: {', '.join(found)})")
    level = "EMERGENCY" if "EMERGENCY" in hits else "URGENT" if "URGENT" in hits else "ROUTINE"
    lines = [f"Suggested urgency: {level}"]
    for lvl, cats in hits.items():
        lines += [f"{lvl}: {c}" for c in cats]
    if level == "ROUTINE":
        lines.append("No red-flag phrases found. Still use judgement on the wording.")
    return "\n".join(lines)


def _sections() -> dict[str, str]:
    text = (DATA / "clinic_info.md").read_text()
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    return {p.split("\n", 1)[0].strip(): p.split("\n", 1)[1].strip() for p in parts}


@tool("Search Clinic Info")
def search_clinic_info(query: str) -> str:
    """Search the clinic's official information (hours, location, fees, services,
    doctors, booking policy, refills, results, vaccinations, screening, telehealth,
    emergencies). Pass a few keywords, e.g. 'fees telehealth'. Returns the best
    matching sections with their titles, to be cited as sources."""
    words = {w for w in re.findall(r"[a-z]+", query.lower()) if len(w) > 2}
    scored = []
    for title, body in _sections().items():
        hay = f"{title} {title} {body}".lower()  # title words count double
        score = sum(hay.count(w) for w in words)
        if score:
            scored.append((score, title, body))
    if not scored:
        return ("No matching section. Available sections: " + ", ".join(_sections())
                + ". Try different keywords.")
    scored.sort(reverse=True)
    return "\n\n".join(f"[section: {t}]\n{b}" for _, t, b in scored[:3])


SERVICE_ALIASES = {
    "chronic care": ["chronic", "diabetes", "blood pressure", "hypertension", "cholesterol", "refill", "review"],
    "child health": ["child", "kid", "baby", "paediatric", "pediatric", "infant"],
    "vaccination": ["vaccin", "jab", "flu shot", "immunis", "immuniz", "hpv"],
    "travel": ["travel", "trip", "overseas"],
    "women's health": ["women", "pap", "contracept", "gynae", "smear"],
    "health screening": ["screening", "check-up", "checkup", "medical check"],
    "minor procedure": ["wound", "stitch", "dressing", "ear wax", "procedure"],
    "telehealth": ["telehealth", "video", "online", "teleconsult"],
}


def _match_service(service: str) -> str:
    s = service.lower()
    for name, keys in SERVICE_ALIASES.items():
        if name in s or any(k in s for k in keys):
            return name
    return "general"


@tool("Find Open Slots")
def find_open_slots(service: str, preferred_day: str = "any") -> str:
    """List open appointment slots in the next 7 days. 'service' is what the patient
    needs (e.g. general, chronic care, child health, vaccination, travel, women's
    health, health screening, minor procedure, telehealth). 'preferred_day' is a
    weekday like 'Tuesday', 'weekend', or 'any'. Returns up to 5 slots. Listing a
    slot does NOT book it."""
    doctors = json.loads((DATA / "doctors.json").read_text())["doctors"]
    svc = _match_service(service)
    pref = preferred_day.strip().lower()[:3]
    now = clinic_today()
    slots = []
    for offset in range(1, 8):  # from tomorrow, so 'today' slots are never stale
        day = now + timedelta(days=offset)
        dow = day.strftime("%a")
        if pref == "wee" and dow != "Sat":  # 'weekend' (clinic is closed Sunday)
            continue
        if pref not in ("", "any", "wee") and dow.lower()[:3] != pref:
            continue
        for doc in doctors:
            if svc not in doc["services"]:
                continue
            for t in doc["weekly"].get(dow, []):
                key = f"{day:%Y-%m-%d}{t}{doc['name']}".encode()
                if hashlib.md5(key).digest()[0] % 3 == 0:  # pretend a third are booked
                    continue
                slots.append((day.date(), t, f"{day:%a %d %b} {t} with {doc['name']}"))
    if not slots:
        return f"No open '{svc}' slots for '{preferred_day}' in the next 7 days. Suggest calling 6123 4567."
    slots.sort()
    picked, per_day = [], {}
    for d, _, label in slots:  # at most 2 per day, so patients get a choice of days
        if per_day.get(d, 0) < 2:
            per_day[d] = per_day.get(d, 0) + 1
            picked.append(label)
    return f"Service matched: {svc}\n" + "\n".join(f"- {s}" for s in picked[:5])
