from api.app.storage import Book


def build_trends(book: Book) -> dict:
    days = {row.get("date", "") for row in book["Sessions"] if row.get("date")}
    return {
        "lifts": _lifts(book),
        "bodyweight": [],
        "nutrition": [],
        "adherence": {
            "supplement_dates": 0,
            "day_dates": len(days),
            "ratio": None if not days else 0.0,
        },
    }


def _number(raw: str) -> float | None:
    if raw is None or str(raw) == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def _shown(value: float) -> float:
    rounded = round(value, 2)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def _session_date(book: Book, session_id: str) -> str:
    for session in book["Sessions"]:
        if session["id"] == session_id:
            return session.get("date", "")
    return ""


def _session_label(book: Book, session_id: str) -> str:
    for session in book["Sessions"]:
        if session["id"] == session_id:
            return session.get("label", "")
    return ""


def _exercise_name(book: Book, row: dict) -> str:
    exercise_id = row.get("exercise_id", "")
    if exercise_id:
        for exercise in book["Exercises"]:
            if exercise["id"] == exercise_id and exercise.get("canonical_name"):
                return exercise["canonical_name"]
    return row.get("name_as_written", "")


def _counts(row: dict) -> tuple[float, float] | None:
    if row.get("set_type") not in ("", "working"):
        return None
    weight = _number(row.get("weight_lb", ""))
    reps = _number(row.get("reps", ""))
    if weight is None or reps is None:
        return None
    return weight, reps


def _lifts(book: Book) -> list[dict]:
    grouped: dict[tuple[str, str], list[tuple[float, float, str]]] = {}
    for row in book["Sets"]:
        counted = _counts(row)
        if counted is None:
            continue
        day = _session_date(book, row.get("session_id", ""))
        name = _exercise_name(book, row)
        if day == "" or name == "":
            continue
        label = _session_label(book, row.get("session_id", ""))
        grouped.setdefault((name, day), []).append((counted[0], counted[1], label))
    lifts = []
    for (name, day), sets in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        weight, _reps, label = max(sets, key=lambda item: item[0])
        best = max(item[0] * (1 + item[1] / 30) for item in sets)
        lifts.append({
            "exercise": name,
            "date": day,
            "label": label,
            "top_weight_lb": _shown(weight),
            "epley": _shown(best),
        })
    return lifts
