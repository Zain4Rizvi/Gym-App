from api.app.schema import TABS
from api.app.storage import encode


def test_tabs_are_the_live_book():
    assert list(TABS) == ["Notes", "Sessions", "Sets", "Exercises", "Aliases"]
    assert "client_request_id" in TABS["Notes"]
    assert "weight_lb" in TABS["Sets"]
    assert "canonical_name" in TABS["Exercises"]


def test_encode_zero_bool_and_null():
    assert encode("weight_lb", 0) == "0"
    assert encode("weight_lb", 0.0) == "0"
    assert encode("weight_lb", None) == ""
    assert encode("needs_review", True) == "TRUE"
    assert encode("needs_review", False) == "FALSE"
    assert encode("needs_review", "TRUE") == "TRUE"
    assert encode("canonical_name", "Bench Press") == "Bench Press"
