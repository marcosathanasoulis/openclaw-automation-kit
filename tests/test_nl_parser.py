"""Tests for NL parser improvements."""
from openclaw_automation.nl import parse_query_to_run, _extract_airport_codes


def test_singapore_airlines_full_name() -> None:
    parsed = parse_query_to_run("Search Singapore Airlines SFO to SIN business")
    assert parsed.script_dir == "library/singapore_award"


def test_sq_alias() -> None:
    parsed = parse_query_to_run("SQ award SFO to NRT economy 2 people")
    assert parsed.script_dir == "library/singapore_award"


def test_bofa_routing() -> None:
    parsed = parse_query_to_run("Check Bank of America balance")
    assert parsed.script_dir == "library/bofa_alert"


def test_bofa_alias() -> None:
    parsed = parse_query_to_run("bofa transactions this month")
    assert parsed.script_dir == "library/bofa_alert"


def test_github_routing() -> None:
    parsed = parse_query_to_run("github login check")
    assert parsed.script_dir == "library/github_signin_check"


def test_common_words_excluded_from_airport_codes() -> None:
    codes = _extract_airport_codes("THE flight FOR ONE person AND MAX budget VIA SFO to NRT")
    assert "THE" not in codes
    assert "FOR" not in codes
    assert "ONE" not in codes
    assert "AND" not in codes
    assert "MAX" not in codes
    assert "VIA" not in codes
    assert "SFO" in codes
    assert "NRT" in codes


def test_ana_excluded_from_airport_codes() -> None:
    codes = _extract_airport_codes("ANA flight from SFO to HND")
    assert "ANA" not in codes
    assert "SFO" in codes
    assert "HND" in codes
