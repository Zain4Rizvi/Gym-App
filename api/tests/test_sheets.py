import os

import pytest

from api.app.schema import TABS
from api.app.storage import insert_row, load_book, save_book


def _title(cell_range: str) -> str:
    return cell_range.split("!")[0].strip("'")


def _write_leaving_tail(tabs: dict, title: str, values: list) -> None:
    old = tabs.get(title, [])
    if len(old) > len(values):
        tabs[title] = values + old[len(values) :]
    else:
        tabs[title] = values


class _Call:
    def __init__(self, fn):
        self._fn = fn

    def execute(self):
        return self._fn()


class FakeValues:
    def __init__(self, tabs: dict):
        self.tabs = tabs

    def get(self, spreadsheetId: str, range: str):
        title = _title(range)
        return _Call(lambda: {"values": [list(row) for row in self.tabs.get(title, [])]})

    def update(self, spreadsheetId: str, range: str, valueInputOption: str, body: dict):
        title = _title(range)

        def run():
            _write_leaving_tail(self.tabs, title, body["values"])
            return {}

        return _Call(run)

    def batchClear(self, spreadsheetId: str, body: dict):
        def run():
            for cell_range in body["ranges"]:
                self.tabs[_title(cell_range)] = []
            return {}

        return _Call(run)

    def batchUpdate(self, spreadsheetId: str, body: dict):
        def run():
            for item in body["data"]:
                _write_leaving_tail(self.tabs, _title(item["range"]), item["values"])
            return {}

        return _Call(run)


class FakeSheets:
    def __init__(self, tabs: dict):
        self.tabs = tabs

    def get(self, spreadsheetId: str):
        return _Call(lambda: {"sheets": [{"properties": {"title": name}} for name in self.tabs]})

    def batchUpdate(self, spreadsheetId: str, body: dict):
        def run():
            for request in body["requests"]:
                self.tabs[request["addSheet"]["properties"]["title"]] = []
            return {}

        return _Call(run)

    def values(self):
        return FakeValues(self.tabs)


class FakeService:
    def __init__(self):
        self.tabs = {"Sheet1": [["keep"]]}

    def spreadsheets(self):
        return FakeSheets(self.tabs)


def test_roundtrip_keeps_extra_columns_and_drops_deleted_rows():
    service = FakeService()
    service.tabs["Days"] = [[
        "bodyweight_lb", "date", "fiber_g", "id", "created_at", "updated_at",
        "source", "sleep_hours", "steps", "day_label", "summary",
    ], [
        "180", "2026-09-22", "12", "abc", "t", "t", "user", "8", "1000", "Push", "",
    ], [
        "181", "2026-09-23", "0", "def", "t", "t", "user", "", "", "", "",
    ]]
    book = load_book(service, "sheet")
    assert book["Days"][0]["fiber_g"] == "12"
    assert book["Days"][0]["date"] == "2026-09-22"
    assert service.tabs["Sheet1"] == [["keep"]]
    book["Days"][0]["bodyweight_lb"] = "179"
    book["Days"] = book["Days"][:1]
    save_book(service, "sheet", book)
    loaded = load_book(service, "sheet")
    assert len(loaded["Days"]) == 1
    assert loaded["Days"][0]["fiber_g"] == "12"
    assert loaded["Days"][0]["bodyweight_lb"] == "179"
    assert loaded["Days"][0]["id"] == "abc"


def test_save_writes_schema_headers_for_a_new_workbook():
    service = FakeService()
    book = load_book(service, "sheet")
    insert_row(book, "Days", {"date": "2026-09-22", "bodyweight_lb": 180})
    save_book(service, "sheet", book)
    assert service.tabs["Days"][0] == TABS["Days"]
    loaded = load_book(service, "sheet")
    assert loaded["Days"][0]["date"] == "2026-09-22"
    assert loaded["Days"][0]["bodyweight_lb"] == "180"


@pytest.mark.skipif(
    not os.getenv("SHEET_ID") or not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"),
    reason="live sheet credentials are not set",
)
def test_live_sheet_roundtrip():
    from api.app.storage import sheets_service

    service = sheets_service()
    book = load_book(service, os.environ["SHEET_ID"])
    if any(row["date"] == "1900-01-01" for row in book["Days"]):
        pytest.skip("probe date is already in the sheet")
    try:
        insert_row(book, "Days", {"date": "1900-01-01", "bodyweight_lb": 1})
        save_book(service, os.environ["SHEET_ID"], book)
        loaded = load_book(service, os.environ["SHEET_ID"])
        probe = next(row for row in loaded["Days"] if row["date"] == "1900-01-01")
        assert probe["bodyweight_lb"] == "1"
    finally:
        from api.app.storage import rebuild_daily_view

        current = load_book(service, os.environ["SHEET_ID"])
        current["Days"] = [row for row in current["Days"] if row["date"] != "1900-01-01"]
        rebuild_daily_view(current)
        save_book(service, os.environ["SHEET_ID"], current)
