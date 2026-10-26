import json
import os
import urllib.error
import urllib.request

_INSTRUCTIONS = (
    "You coach this one person from their gym log. "
    "The log is the only record you have. "
    "Answer the question from that log. "
    "When a weight, meal, or day is missing, say it was not logged. "
    "Do not invent numbers. "
    "Photos are not in the log. "
    "You only talk. You cannot change the log. "
    "Keep the answer to a few plain sentences. Do not use markdown."
)
# ponytail: Groq on-demand TPM is 8000 for the current model. Raise this when the tier allows the whole book.
_MAX_LOG_CHARS = 10000
_SKIP_FIELDS = {
    "id",
    "created_at",
    "updated_at",
    "source",
    "client_request_id",
    "parsed_json",
    "error_text",
    "model",
    "prompt_version",
    "parse_status",
    "storage_uri",
    "exercise_id",
    "session_id",
    "note_id",
}


def log_text(book: dict) -> str:
    sessions = {row.get("id"): row for row in book.get("Sessions", [])}
    names = {row.get("id"): row.get("canonical_name", "") for row in book.get("Exercises", [])}
    sections: list[tuple[str, list[str]]] = []
    for tab, rows in book.items():
        # DailyView repeats the other tabs. Media is photos.
        if tab in {"Media", "DailyView"}:
            continue
        lines = []
        for row in rows:
            if tab == "Sets":
                line = _set_line(row, sessions.get(row.get("session_id"), {}), names.get(row.get("exercise_id"), ""))
            else:
                line = _fact_line(row)
            if line:
                lines.append(line)
        if lines:
            sections.append((tab, lines))
    return _fit(sections)


def _fact_line(row: dict) -> str:
    parts = [f"{key} {value}" for key, value in row.items() if key not in _SKIP_FIELDS and str(value) != ""]
    return " ".join(parts)


def _set_line(row: dict, session: dict, canonical: str) -> str:
    parts = []
    if session.get("date"):
        parts.append(session["date"])
    if session.get("label"):
        parts.append(session["label"])
    name = row.get("name_as_written") or canonical
    if name:
        parts.append(name)
    if canonical and canonical != name:
        parts.append(f"({canonical})")
    weight = str(row.get("weight_lb") or "")
    reps = str(row.get("reps") or "")
    unit = str(row.get("unit_entered") or "")
    if weight and reps:
        parts.append(f"{weight}{unit} x {reps}")
    elif weight:
        parts.append(f"{weight}{unit}")
    elif reps:
        parts.append(f"x {reps}")
    if str(row.get("set_number") or ""):
        parts.append(f"set {row['set_number']}")
    if str(row.get("set_type") or ""):
        parts.append(str(row["set_type"]))
    if str(row.get("rpe") or ""):
        parts.append(f"rpe {row['rpe']}")
    if str(row.get("variation") or ""):
        parts.append(str(row["variation"]))
    return " ".join(parts)


def _fit(sections: list[tuple[str, list[str]]]) -> str:
    def render(omitted: bool) -> str:
        chunks = []
        if omitted:
            chunks.append("Some older rows were left out so the question fits the model.")
        for title, lines in sections:
            if not lines:
                continue
            chunks.append(title)
            chunks.extend(lines)
        return "\n".join(chunks)

    omitted = False
    while len(render(omitted)) > _MAX_LOG_CHARS:
        longest = max(sections, key=lambda item: sum(len(line) + 1 for line in item[1]), default=None)
        if longest is None or not longest[1]:
            break
        longest[1].pop(0)
        omitted = True
    return render(omitted)


def normalize_messages(raw) -> list[dict]:
    if not isinstance(raw, list) or not raw or len(raw) > 40:
        raise ValueError("messages is required")
    cleaned = []
    for item in raw:
        if not isinstance(item, dict):
            raise ValueError("messages is required")
        role = item.get("role")
        content = item.get("content")
        if role not in {"user", "assistant"} or not isinstance(content, str):
            raise ValueError("messages is required")
        text = content.strip()
        if text == "" or len(text) > 4000:
            raise ValueError("messages is required")
        cleaned.append({"role": role, "content": text})
    if cleaned[-1]["role"] != "user":
        raise ValueError("messages is required")
    return cleaned


def ask(book: dict, messages: list[dict], complete) -> str:
    system = _INSTRUCTIONS + "\n\nlog:\n" + log_text(book)
    reply = str(complete(system, messages) or "").strip()
    if reply == "":
        raise RuntimeError("empty coach reply")
    return reply


def configured_coach():
    if os.getenv("GROQ_API_KEY") or os.getenv("GEMINI_API_KEY"):
        return complete_chat
    return None


def complete_chat(system: str, messages: list[dict]) -> str:
    if os.getenv("GROQ_API_KEY"):
        return _groq_chat(system, messages)
    return _gemini_chat(system, messages)


def _groq_chat(system: str, messages: list[dict]) -> str:
    key = os.environ["GROQ_API_KEY"]
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system}, *messages],
    }
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "gym-app/1.0",
        },
        method="POST",
    )
    payload = _read_json(request, "groq", 60)
    message = payload["choices"][0]["message"]
    return (message.get("content") or message.get("reasoning") or "").strip()


def _gemini_chat(system: str, messages: list[dict]) -> str:
    key = os.environ["GEMINI_API_KEY"]
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    contents = [
        {"role": "user" if item["role"] == "user" else "model", "parts": [{"text": item["content"]}]}
        for item in messages
    ]
    body = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    payload = _read_json(request, "gemini", 60)
    return payload["candidates"][0]["content"]["parts"][0]["text"].strip()


def _read_json(request: urllib.request.Request, name: str, timeout: int) -> dict:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"{name} {exc.code}: {detail}") from exc
    return json.loads(raw.decode())
