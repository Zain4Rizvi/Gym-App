import re
from datetime import date

MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "alr": 4, "ape": 4,
}
LABELS = {
    "push": "Push", "pull": "Pull", "legs": "Legs", "leg": "Legs",
    "arms": "Other", "shoulders": "Other", "upper": "Other", "lower": "Other",
}
BARBELL = {"Bench Press", "Incline Bench Press", "Barbell Squat", "Deadlift", "Romanian Deadlift"}
BODYWEIGHT = {"Pull Up", "Chin Up", "Dip", "Push Up"}
STOP = {
    "push", "pull", "legs", "leg", "arms", "shoulders", "upper", "lower",
    "last", "set", "sets", "next", "time", "for", "and", "the", "with", "good",
    "weak", "plan", "first", "keep", "work", "still", "try", "light", "strong",
}

# Longest aliases first. The log repeats the same lift under several spellings.
ALIASES = [
    ("incline dumbbell press", "Incline Dumbbell Press"),
    ("incline dumbbell", "Incline Dumbbell Press"),
    ("incline dumbell press", "Incline Dumbbell Press"),
    ("incline dumbell", "Incline Dumbbell Press"),
    ("incline db press", "Incline Dumbbell Press"),
    ("idbp", "Incline Dumbbell Press"),
    ("incline bench", "Incline Bench Press"),
    ("incline smith", "Incline Smith Press"),
    ("incline chest press", "Incline Chest Press"),
    ("incline machine press", "Incline Chest Press"),
    ("incline machine", "Incline Chest Press"),
    ("incline press", "Incline Chest Press"),
    ("flat dumbbell", "Dumbbell Bench Press"),
    ("flat dumbell", "Dumbbell Bench Press"),
    ("chest press", "Chest Press"),
    ("bench press", "Bench Press"),
    ("bench pr", "Bench Press"),
    ("bench", "Bench Press"),
    ("lat pull down", "Lat Pulldown"),
    ("lat pulldown", "Lat Pulldown"),
    ("lat pull-down", "Lat Pulldown"),
    ("pull down", "Lat Pulldown"),
    ("pull-down", "Lat Pulldown"),
    ("pulldown", "Lat Pulldown"),
    ("front pull down", "Front Pulldown"),
    ("front pull-down", "Front Pulldown"),
    ("close grip pull-down", "Close Grip Pulldown"),
    ("close grip pull down", "Close Grip Pulldown"),
    ("close grip lat pull-down", "Close Grip Pulldown"),
    ("neutral grip pull down", "Neutral Grip Pulldown"),
    ("dual pulley pull down", "Dual Pulley Pulldown"),
    ("dual pulley pull-down", "Dual Pulley Pulldown"),
    ("dual pull down", "Dual Pulley Pulldown"),
    ("dual pull-down", "Dual Pulley Pulldown"),
    ("good handle pull-down", "Lat Pulldown"),
    ("good handle pull down", "Lat Pulldown"),
    ("good grip pull-down", "Lat Pulldown"),
    ("good bar pull down", "Lat Pulldown"),
    ("seated row", "Seated Row"),
    ("seated rows", "Seated Row"),
    ("rows", "Seated Row"),
    ("row", "Seated Row"),
    ("upper back seated row", "Seated Row"),
    ("upper back row", "Seated Row"),
    ("low row", "Low Row"),
    ("mts row", "MTS Row"),
    ("horizontal row", "Horizontal Row"),
    ("underhand row", "Underhand Row"),
    ("t bar", "T Bar Row"),
    ("y bar", "T Bar Row"),
    ("barbell row", "Barbell Row"),
    ("leg press", "Leg Press"),
    ("leg extension", "Leg Extension"),
    ("leg curl", "Leg Curl"),
    ("lying hamstring curl", "Leg Curl"),
    ("hamstring curl", "Leg Curl"),
    ("hack squat", "Hack Squat"),
    ("hammer squat", "Hammer Squat"),
    ("pendulum squat", "Pendulum Squat"),
    ("barbell squat", "Barbell Squat"),
    ("squat", "Barbell Squat"),
    ("romanian deadlift", "Romanian Deadlift"),
    ("rdl", "Romanian Deadlift"),
    ("hip abductor", "Hip Abductor"),
    ("back extension", "Back Extension"),
    ("seated calf raise", "Calf Raise"),
    ("standing calf raise", "Calf Raise"),
    ("calf raise", "Calf Raise"),
    ("calves", "Calf Raise"),
    ("shoulder press", "Shoulder Press"),
    ("dumbbell shoulder press", "Dumbbell Shoulder Press"),
    ("dumbell shoulder press", "Dumbbell Shoulder Press"),
    ("overhead press", "Shoulder Press"),
    ("lateral raise", "Lateral Raise"),
    ("lateral raises", "Lateral Raise"),
    ("lat raise", "Lateral Raise"),
    ("lat raises", "Lateral Raise"),
    ("cable lat raise", "Lateral Raise"),
    ("incline bicep curl", "Incline Bicep Curl"),
    ("incline dumbbell curl", "Incline Bicep Curl"),
    ("incline dumbell curl", "Incline Bicep Curl"),
    ("incline hammer curl", "Incline Hammer Curl"),
    ("preacher curls", "Preacher Curl"),
    ("preacher curl", "Preacher Curl"),
    ("preacher", "Preacher Curl"),
    ("hammer curl", "Hammer Curl"),
    ("hammer curls", "Hammer Curl"),
    ("bicep curl", "Bicep Curl"),
    ("biceps curl", "Bicep Curl"),
    ("standing curl", "Bicep Curl"),
    ("curls", "Bicep Curl"),
    ("tricep pushdown", "Tricep Pushdown"),
    ("tricep push down", "Tricep Pushdown"),
    ("trciep press", "Tricep Press"),
    ("tricep press", "Tricep Press"),
    ("tricep overhead", "Tricep Overhead"),
    ("overhead tricep", "Tricep Overhead"),
    ("skull crusher", "Skull Crusher"),
    ("skull crushers", "Skull Crusher"),
    ("tricep extension", "Tricep Extension"),
    ("chest fly", "Chest Fly"),
    ("cheat fly", "Chest Fly"),
    ("machine chest fly", "Chest Fly"),
    ("pec fly", "Chest Fly"),
    ("pec dec", "Pec Dec"),
    ("rear delt fly", "Rear Delt Fly"),
    ("rear delt", "Rear Delt Fly"),
    ("dear delt", "Rear Delt Fly"),
    ("assisted pull up", "Assisted Pull Up"),
    ("pull up", "Pull Up"),
    ("pull ups", "Pull Up"),
    ("chin up", "Chin Up"),
    ("push up", "Push Up"),
    ("push-ups", "Push Up"),
    ("push ups", "Push Up"),
    ("dips", "Dip"),
    ("dip", "Dip"),
    ("shrug", "Shrug"),
    ("shrugs", "Shrug"),
    ("ab crunch", "Ab Crunch"),
    ("abs", "Ab Crunch"),
]
ALIASES.sort(key=lambda item: len(item[0]), reverse=True)

TOKEN = re.compile(
    r"(?i)(?P<year>\b20\d{2}\b)"
    r"|(?P<no>no\.\s*(?P<noday>\d{1,2}))"
    r"|(?P<mon>jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?|alr|ape)\.?\s+(?P<day>\d{1,2})(?:st|nd|rd|th)?"
)
GENERIC = re.compile(r"([A-Za-z][A-Za-z'’+-]*(?:\s+[A-Za-z][A-Za-z'’+-]*){0,3})\s+(?=\d|pr\b|failed\b)", re.I)
PLATE = re.compile(r"(\d+(?:\.\d+)?)\s+plates?(?:\s*\+\s*(\d+(?:\.\d+)?))?", re.I)
PLUS = re.compile(r"(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)")
SIDE = re.compile(r"(\d+(?:\.\d+)?)\s+each\s+side", re.I)
PAIR = re.compile(r"(\d+(?:\.\d+)?)\s*[x×\-]\s*(\d+(?:\.\d+)?)")
BARE = re.compile(r"\d+(?:\.\d+)?")


def parse_log(text: str) -> list[dict]:
    cleaned = text.replace("\u2019", "'").replace("\u2013", " ").replace("\u2014", " ")
    cleaned = re.sub(r"(\d)\s+\.\s*(\d)", r"\1.\2", cleaned)
    events = []
    for match in TOKEN.finditer(cleaned):
        if match.group("year"):
            events.append(("year", int(match.group("year")), match.start(), match.end()))
            continue
        if match.group("no"):
            month, day = 11, int(match.group("noday"))
        else:
            if match.group("mon").lower().startswith("dec"):
                before = cleaned[max(0, match.start() - 4):match.start()].lower()
                if before.endswith("pec "):
                    continue
            month = _month(match.group("mon"))
            day = int(match.group("day"))
        if day < 1 or day > 31:
            continue
        events.append(("date", month, day, match.start(), match.end()))

    year = 2022
    explicit = False
    last_month = 0
    sessions = []
    dates = [item for item in events if item[0] == "date"]
    for index, event in enumerate(events):
        if event[0] == "year":
            if event[1] >= year:
                year = event[1]
                explicit = True
            continue
        _, month, day, _start, end = event
        if last_month >= 10 and month <= 3 and not explicit:
            year += 1
        try:
            current = date(year, month, day)
        except ValueError:
            continue
        explicit = False
        last_month = month
        nxt = next((item[3] for item in events[index + 1:] if item[0] == "date"), len(cleaned))
        body = cleaned[end:nxt].strip()
        label, exercises = _body(body)
        if not exercises:
            continue
        sessions.append({
            "date": current.isoformat(),
            "label": label,
            "text": body,
            "exercises": exercises,
        })
    return sessions


def _month(raw: str) -> int:
    key = raw.lower()[:4]
    if key.startswith("alr") or key.startswith("ape"):
        return 4
    return MONTHS[key[:3]]


def _body(text: str) -> tuple[str, list[dict]]:
    label = ""
    stripped = text.lstrip(" -")
    first = stripped.split(" ", 1)[0].strip("():,").lower()
    second = ""
    if first:
        rest = stripped[len(stripped.split(" ", 1)[0]):].lstrip()
        second = rest.split(" ", 1)[0].strip("():,").lower()
    exercise_start = any(stripped.lower().startswith(alias) for alias, _canon in ALIASES)
    if first in LABELS and not exercise_start:
        label = LABELS[first]
        stripped = stripped[len(stripped.split(" ", 1)[0]):].lstrip(" -")
    names = _names(stripped)
    exercises = []
    for index, (start, end, name) in enumerate(names):
        stop = names[index + 1][0] if index + 1 < len(names) else len(stripped)
        sets = _sets(stripped[end:stop], name)
        if not sets:
            continue
        current = exercises[-1] if exercises and exercises[-1]["name"] == name else None
        if current is None:
            exercises.append({"name": name, "sets": sets})
        else:
            current["sets"].extend(sets)
    return label, exercises


def _names(text: str) -> list[tuple[int, int, str]]:
    lower = text.lower()
    found = []
    pos = 0
    while pos < len(text):
        if not text[pos].isalnum():
            pos += 1
            continue
        alias = next((
            (pos, pos + len(raw), canon)
            for raw, canon in ALIASES
            if lower.startswith(raw, pos) and (pos + len(raw) == len(text) or not lower[pos + len(raw)].isalpha())
        ), None)
        if alias:
            found.append(alias)
            pos = alias[1]
            continue
        generic = GENERIC.match(text, pos)
        if generic:
            words = generic.group(1).strip()
            parts = words.lower().split()
            blocked = {"x", "plate", "plates", "pr", "reps", "rep", "each", "side", "lb", "lbs"}
            if len(words) >= 3 and words.lower() not in STOP and not any(part in blocked for part in parts):
                found.append((generic.start(1), generic.end(1), _title(words)))
            pos = generic.end(1)
            continue
        pos += 1
    return found


def _title(words: str) -> str:
    return " ".join(part[:1].upper() + part[1:] for part in words.split())


def _sets(text: str, exercise: str) -> list[dict]:
    chunk = text.replace("(", " ").replace(")", " ")
    chunk = re.sub(r"\bfail(?:ed)?\s+\d+(?:\.\d+)?", " ", chunk, flags=re.I)
    chunk = re.sub(r"\d+(?:\.\d+)?\s+fail(?:ed)?\b", " ", chunk, flags=re.I)
    patterns = (
        ("plate", re.compile(r"(\d+(?:\.\d+)?)\s+plates?(?:\s*\+\s*(\d+(?:\.\d+)?))?\s*[x×]\s*(\d+(?:\.\d+)?)", re.I)),
        ("plus", re.compile(r"(\d+(?:\.\d+)?)\s*\+\s*(\d+(?:\.\d+)?)\s*[x×]\s*(\d+(?:\.\d+)?)")),
        ("side", re.compile(r"(\d+(?:\.\d+)?)\s+each\s+side(?:\s*[x×]\s*(\d+(?:\.\d+)?))?", re.I)),
        ("pair", re.compile(r"(\d+(?:\.\d+)?)\s*[x×\-]\s*(\d+(?:\.\d+)?)")),
        ("comma", re.compile(r"(\d+(?:\.\d+)?)\s*,\s*(\d+(?:\.\d+)?)(?:\s*reps\b|(?!\s*[x×\-]))", re.I)),
        ("pr", re.compile(r"\bpr\s+(\d+(?:\.\d+)?)", re.I)),
        ("bare", re.compile(r"\d+(?:\.\d+)?")),
    )
    found = []
    pos = 0
    while pos < len(chunk):
        matched = None
        for kind, pattern in patterns:
            found_at = pattern.match(chunk, pos)
            if found_at:
                matched = (kind, found_at)
                break
        if matched is None:
            pos += 1
            continue
        kind, match = matched
        weight, reps = _read_set(kind, match, exercise)
        if exercise in BODYWEIGHT and kind == "comma" and weight is not None and weight <= 30 and reps and reps <= 30:
            found.append({"weight": None, "reps": weight})
            found.append({"weight": None, "reps": reps})
        elif reps and reps > 0 and not (exercise in BODYWEIGHT and weight is not None and weight >= 25):
            if exercise in BODYWEIGHT and weight is None:
                found.append({"weight": None, "reps": reps})
            elif weight and weight > 0 and exercise not in BODYWEIGHT:
                found.append({"weight": round(weight, 2), "reps": reps})
        pos = match.end()
    return found


def _read_set(kind: str, match: re.Match, exercise: str) -> tuple[float | None, float | None]:
    if kind == "plate":
        extra = float(match.group(2) or 0)
        return _plates(float(match.group(1)), exercise) + extra, float(match.group(3))
    if kind == "plus":
        return _plates(float(match.group(1)), exercise) + float(match.group(2)), float(match.group(3))
    if kind == "side":
        reps = float(match.group(2)) if match.group(2) else None
        return float(match.group(1)) * 2, reps
    if kind == "pair":
        return float(match.group(1)), float(match.group(2))
    if kind == "comma":
        return float(match.group(1)), float(match.group(2))
    if kind == "pr":
        return float(match.group(1)), 1
    number = float(match.group(0))
    if 2000 <= number <= 2099:
        return None, None
    if exercise in BODYWEIGHT and number <= 30:
        return None, number
    if exercise not in BODYWEIGHT and number >= 45:
        return number, 1
    return None, None


def _plates(count: float, exercise: str) -> float:
    if exercise in BARBELL:
        return 45 + 90 * count
    return 45 * count
