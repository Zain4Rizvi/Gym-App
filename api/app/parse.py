import json
import os
import re
import urllib.error
import urllib.request

from api.app.schema import SET_TYPES
from api.app.storage import apply_fields, delete_row, insert_row, patch_row

PROMPT_VERSION = "v1"
_NUMBER = re.compile(r"^(?:0|[1-9]\d*)(?:\.\d+)?$")
_COMPARE = ("weight_lb", "reps", "rpe", "set_type")
_SESSION_TEXT = ("start_time", "end_time", "session_notes")


def model_input(note: dict, book) -> dict:
    return {
        "raw_text": note.get("raw_text", ""),
        "day_label": note.get("day_label", ""),
        "catalog": {
            "exercises": [
                {"id": row["id"], "canonical_name": row["canonical_name"]}
                for row in book["Exercises"]
            ],
            "aliases": [
                {"alias": row["alias"], "exercise_id": row["exercise_id"], "day_label": row["day_label"]}
                for row in book["Aliases"]
            ],
        },
    }


def configured_model():
    if os.getenv("GROQ_API_KEY"):
        return groq_complete
    if os.getenv("GEMINI_API_KEY"):
        return gemini_complete
    return None


def active_model_name() -> str:
    if os.getenv("GROQ_API_KEY"):
        return os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    return os.getenv("GEMINI_MODEL", "gemini-2.5-flash")


def _prompt(info: dict) -> str:
    return (
        "Transcribe one lift note into JSON. The typed note is the record. "
        "Do not invent a movement, weight, reps, RPE, or set type. "
        "Copy name_as_written exactly, including typos. "
        "Do not merge two exercises and do not attach a number-only line to a previous exercise. "
        "Use day_label so a day-specific alias beats a blank day_label. "
        "Do not assign a different exercise to force a match. "
        "weight and reps are the tokens as written, or empty if that slot is absent. "
        "Keep uncertain tokens as written, such as 80 ish, 70 z, i op, 6?, and AMRAP. "
        "An exercise with no sets has sets: []. "
        "A trailing x with no reps has the weight token and empty reps. "
        "unit is kg only when the note says kg, otherwise lb when a weight is present, otherwise empty. "
        "rpe is the number only when the note states it; @8 is 8. "
        "set_type is warmup, working, drop, or failure only when the note states it. "
        "variation only when stated. unsure is true when a token is uncertain. "
        "start_time, end_time, and session_notes are empty strings unless the note states them.\n"
        f"prompt_version: {PROMPT_VERSION}\n"
        f"day_label: {info['day_label']}\n"
        f"catalog: {json.dumps(info['catalog'], ensure_ascii=False)}\n"
        "note:\n"
        f"{info['raw_text']}"
    )


def gemini_complete(info: dict) -> dict:
    # ponytail: no billing probe; key must be a billed project (paid terms do not train on prompts). Unpaid quota does — use Vertex if this key is free-tier.
    key = os.environ["GEMINI_API_KEY"]
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"role": "user", "parts": [{"text": _prompt(info)}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"gemini {exc.code}: {detail}") from exc
    payload = json.loads(raw.decode())
    text = payload["candidates"][0]["content"]["parts"][0]["text"]
    return _json_object(text)


def groq_complete(info: dict) -> dict:
    key = os.environ["GROQ_API_KEY"]
    model = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Return one JSON object and nothing else."},
            {"role": "user", "content": _prompt(info)},
        ],
        "response_format": {"type": "json_object"},
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
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:500]
        raise RuntimeError(f"groq {exc.code}: {detail}") from exc
    payload = json.loads(raw.decode())
    message = payload["choices"][0]["message"]
    text = message.get("content") or message.get("reasoning") or ""
    return _json_object(text)


def _json_object(text: str) -> dict:
    raw = str(text or "").strip()
    try:
        found = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("model payload is not an object")
        found = json.loads(raw[start:end + 1])
    if not isinstance(found, dict):
        raise ValueError("model payload is not an object")
    return found


def _stated_label(note: dict) -> str:
    current = note.get("day_label", "")
    if current:
        return current
    for line in note.get("raw_text", "").splitlines():
        text = line.strip()
        if not text:
            continue
        for label in ("Push", "Pull", "Legs", "Other"):
            if text.casefold() == label.casefold():
                return label
        break
    return ""


def _plain(value) -> tuple[str, bool]:
    if value is None:
        return "", False
    text = str(value).strip()
    if text == "":
        return "", False
    if _NUMBER.fullmatch(text) is None:
        return "", True
    number = float(text)
    if number.is_integer():
        return str(int(number)), False
    return format(number, "g"), False


def _rpe(value) -> tuple[str, bool]:
    if value is None:
        return "", False
    text = str(value).strip()
    if text.startswith("@") and _NUMBER.fullmatch(text[1:]):
        return _plain(text[1:])
    return _plain(value)


def _set_type(value) -> tuple[str, bool]:
    if value is None:
        return "", False
    text = str(value).strip()
    if text == "":
        return "", False
    folded = text.casefold()
    if folded in SET_TYPES:
        return folded, False
    return "", True


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def plan_sets(payload: dict) -> list[dict]:
    if not isinstance(payload, dict):
        raise ValueError("model payload is not an object")
    exercises = payload.get("exercises")
    if not isinstance(exercises, list):
        raise ValueError("model payload has no exercises")
    planned = []
    for exercise in exercises:
        if not isinstance(exercise, dict):
            raise ValueError("exercise is not an object")
        name = _text(exercise.get("name_as_written"))
        raw_sets = exercise.get("sets")
        if not isinstance(raw_sets, list):
            raise ValueError("sets is not a list")
        if name == "" and not raw_sets:
            continue
        for index, slot in enumerate(raw_sets or [{}], start=1):
            if not isinstance(slot, dict):
                raise ValueError("set is not an object")
            weight, weight_bad = _plain(slot.get("weight"))
            reps, reps_bad = _plain(slot.get("reps"))
            rpe, rpe_bad = _rpe(slot.get("rpe"))
            set_type, type_bad = _set_type(slot.get("set_type"))
            review = slot.get("unsure") is True or weight_bad or reps_bad or rpe_bad or type_bad
            if (weight != "" and reps == "") or (weight == "" and reps == ""):
                review = True
            unit = _text(slot.get("unit")).casefold()
            if weight == "":
                unit = ""
            elif unit != "kg":
                unit = "lb"
            planned.append({
                "name_as_written": name,
                "set_number": str(index),
                "weight": weight,
                "unit": unit,
                "reps": reps,
                "rpe": rpe,
                "set_type": set_type,
                "variation": _text(slot.get("variation")),
                "needs_review": review,
            })
    if not planned:
        raise ValueError("no sets")
    return planned


def _find_exercise(book, name: str, day_label: str) -> str | None:
    folded = name.casefold()
    for label in ((day_label, "") if day_label else ("",)):
        for alias in book["Aliases"]:
            if alias["alias"].casefold() == folded and alias["day_label"] == label and alias["exercise_id"]:
                return alias["exercise_id"]
    for exercise in book["Exercises"]:
        if exercise["canonical_name"].strip().casefold() == folded:
            return exercise["id"]
    return None


def _mark_unknown(book, day_label: str, planned: list[dict]) -> None:
    missing = {
        item["name_as_written"].casefold()
        for item in planned
        if item["name_as_written"] and _find_exercise(book, item["name_as_written"], day_label) is None
    }
    for item in planned:
        if item["name_as_written"] == "" or item["name_as_written"].casefold() in missing:
            item["needs_review"] = True


def _fields(item: dict, session_id: str, note_id: str, exercise_id: str) -> dict:
    fields = {
        "session_id": session_id,
        "note_id": note_id,
        "exercise_id": exercise_id,
        "name_as_written": item["name_as_written"],
        "set_number": item["set_number"],
        "reps": item["reps"],
        "rpe": item["rpe"],
        "set_type": item["set_type"],
        "variation": item["variation"],
        "needs_review": item["needs_review"],
        "edited_by_user": False,
        "source": "gemini",
    }
    if item["weight"] != "":
        fields["weight_lb"] = item["weight"]
        fields["unit_entered"] = item["unit"] or "lb"
    return fields


def _materialize(fields: dict) -> dict:
    row: dict = {}
    apply_fields("Sets", row, fields)
    return row


def _exercise_id(book, name: str, day_label: str, cache: dict[str, str]) -> str:
    if name == "":
        return ""
    key = name.casefold()
    if key in cache:
        return cache[key]
    found = _find_exercise(book, name, day_label)
    if found is None:
        found = insert_row(
            book,
            "Exercises",
            {"canonical_name": name, "status": "proposed", "source": "gemini"},
        )["id"]
    cache[key] = found
    return found


def _ensure_session(book, note: dict, payload: dict) -> dict:
    extra = {}
    for key in _SESSION_TEXT:
        text = _text(payload.get(key))
        if text:
            extra[key] = text
    found = next((row for row in book["Sessions"] if row["note_id"] == note["id"]), None)
    if found is None:
        return insert_row(book, "Sessions", {
            "date": note.get("session_date", ""),
            "label": note.get("day_label", ""),
            "note_id": note["id"],
            "source": "gemini",
            **extra,
        })
    fill = {key: value for key, value in extra.items() if found.get(key, "") == ""}
    if fill:
        return patch_row(book, "Sessions", found["id"], fill)
    return found


def _result(book, note: dict, conflicts: list) -> dict:
    sets = [row for row in book["Sets"] if row["note_id"] == note["id"]]
    return {"note": note, "sets": sets, "conflicts": conflicts}


def run_parse(book, note: dict, model, overwrite_set_ids: list | None) -> dict:
    stated = _stated_label(note)
    if stated and stated != note.get("day_label", ""):
        note = patch_row(book, "Notes", note["id"], {"day_label": stated})
    try:
        payload = model(model_input(note, book))
        planned = plan_sets(payload)
        dumped = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except Exception as exc:
        patch_row(book, "Notes", note["id"], {"parse_status": "error", "error_text": str(exc)})
        return _result(book, note, [])

    day = note.get("day_label", "")
    _mark_unknown(book, day, planned)
    kept = [
        row for row in book["Sets"]
        if row["note_id"] == note["id"] and (row["edited_by_user"] == "TRUE" or row["source"] != "gemini")
    ]
    conflicts = []
    paired = []
    for item in planned:
        stored = _materialize(_fields(item, "", note["id"], ""))
        match = next(
            (
                row for row in kept
                if (str(row["set_number"]), row["name_as_written"].casefold())
                == (item["set_number"], item["name_as_written"].casefold())
            ),
            None,
        )
        if match is not None and any(match.get(key, "") != stored.get(key, "") for key in _COMPARE):
            conflicts.append({
                "set_id": match["id"],
                "name_as_written": match["name_as_written"],
                "set_number": match["set_number"],
                "fields": [key for key in _COMPARE if match.get(key, "") != stored.get(key, "")],
            })
        paired.append((item, match))
    if conflicts and overwrite_set_ids is None:
        return _result(book, note, conflicts)

    overwrite = {str(item) for item in (overwrite_set_ids or [])}
    conflict_ids = {item["set_id"] for item in conflicts}
    session = _ensure_session(book, note, payload)
    doomed = [
        row["id"] for row in book["Sets"]
        if row["note_id"] == note["id"] and row["source"] == "gemini" and row["edited_by_user"] != "TRUE"
    ]
    for row_id in doomed:
        delete_row(book, "Sets", row_id)
    cache: dict[str, str] = {}
    for item, match in paired:
        fields = _fields(item, session["id"], note["id"], _exercise_id(book, item["name_as_written"], day, cache))
        if match is not None and match["id"] not in doomed:
            if match["id"] in overwrite and match["id"] in conflict_ids:
                patch_row(book, "Sets", match["id"], fields)
            continue
        insert_row(book, "Sets", fields)
    patch_row(book, "Notes", note["id"], {
        "parse_status": "done",
        "error_text": None,
        "model": active_model_name(),
        "prompt_version": PROMPT_VERSION,
        "parsed_json": dumped,
    })
    return _result(book, note, [])
