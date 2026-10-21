from api.app.schema import BOOL_FIELDS, TABS


class Book(dict):
    def __init__(self):
        super().__init__((name, []) for name in TABS)
        self.dirty = False
        self.headers: dict[str, list[str]] = {}


def empty_book() -> Book:
    return Book()


def encode(field: str, value) -> str:
    if value is None:
        return ""
    if field in BOOL_FIELDS or isinstance(value, bool):
        if value is True or value == "TRUE":
            return "TRUE"
        if value is False or value == "FALSE":
            return "FALSE"
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return format(value, "g")
    return str(value)
