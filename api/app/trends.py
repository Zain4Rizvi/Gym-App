from datetime import date, timedelta

from api.app.storage import Book


def build_trends(book: Book) -> dict:
    return {
        "lifts": _lifts(book),
        "bodyweight": _bodyweight(book),
        "nutrition": _nutrition(book),
        "adherence": _adherence(book),
        "muscles": _muscles(book),
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


def _bodyweight(book: Book) -> list[dict]:
    by_date: dict[str, float] = {}
    for row in book["Days"]:
        weight = _number(row.get("bodyweight_lb", ""))
        day = row.get("date", "")
        if weight is None or day == "":
            continue
        by_date[day] = weight
    points = []
    for day in sorted(by_date):
        current = date.fromisoformat(day)
        window = []
        for offset in range(7):
            key = (current - timedelta(days=offset)).isoformat()
            if key in by_date:
                window.append(by_date[key])
        points.append({
            "date": day,
            "bodyweight_lb": _shown(by_date[day]),
            "mean_7d": _shown(sum(window) / len(window)),
        })
    return points


def _nutrition(book: Book) -> list[dict]:
    points = []
    for row in sorted(book["Nutrition"], key=lambda item: item.get("date", "")):
        day = row.get("date", "")
        if day == "":
            continue
        calories = _number(row.get("calories", ""))
        protein = _number(row.get("protein_g", ""))
        points.append({
            "date": day,
            "calories": None if calories is None else _shown(calories),
            "protein_g": None if protein is None else _shown(protein),
        })
    return points


def _adherence(book: Book) -> dict:
    supplement_dates = {row["date"] for row in book["Supplements"] if row.get("date")}
    day_dates = {row["date"] for row in book["Days"] if row.get("date")}
    ratio = None if not day_dates else len(supplement_dates) / len(day_dates)
    return {
        "supplement_dates": len(supplement_dates),
        "day_dates": len(day_dates),
        "ratio": ratio,
    }


def _muscles(book: Book) -> list[dict]:
    # ponytail: split comma-separated primary_muscles at read time; a muscle table waits until a muscle needs its own columns
    totals: dict[tuple[str, str], float] = {}
    for row in book["Sets"]:
        counted = _counts(row)
        if counted is None:
            continue
        day = _session_date(book, row.get("session_id", ""))
        if day == "":
            continue
        try:
            current = date.fromisoformat(day)
        except ValueError:
            continue
        week = (current - timedelta(days=current.weekday())).isoformat()
        weight, reps = counted
        volume = weight * reps
        for muscle in _primary_muscles(book, row):
            totals[(muscle, week)] = totals.get((muscle, week), 0) + volume
    return [
        {"muscle": muscle, "week": week, "volume": _shown(volume)}
        for (muscle, week), volume in sorted(totals.items())
    ]


def _primary_muscles(book: Book, row: dict) -> list[str]:
    exercise_id = row.get("exercise_id", "")
    raw = ""
    for exercise in book["Exercises"]:
        if exercise["id"] == exercise_id:
            raw = exercise.get("primary_muscles", "")
            break
    return [part.strip() for part in raw.split(",") if part.strip()]
