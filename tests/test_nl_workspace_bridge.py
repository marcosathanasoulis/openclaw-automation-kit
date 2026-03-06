from __future__ import annotations

from datetime import date

from openclaw_automation.nl import parse_query_to_run


def test_meetings_query_routes_to_google_workspace() -> None:
    parsed = parse_query_to_run("Tell me my meetings on Monday")
    assert parsed.script_dir == "examples/google_workspace_brief"
    assert parsed.inputs["task"] == "meetings"
    assert "account_email" not in parsed.inputs


def test_email_query_routes_to_google_workspace() -> None:
    parsed = parse_query_to_run("Show my latest emails from Gmail")
    assert parsed.script_dir == "examples/google_workspace_brief"
    assert parsed.inputs["task"] == "emails"
    assert parsed.inputs["gmail_query"] == "newer_than:7d"


def test_brief_query_routes_to_google_workspace() -> None:
    parsed = parse_query_to_run("Give me my calendar and email brief for today")
    assert parsed.script_dir == "examples/google_workspace_brief"
    assert parsed.inputs["task"] == "brief"
    assert parsed.inputs["date"] == date.today().isoformat()


def test_last_time_sender_email_query() -> None:
    parsed = parse_query_to_run("When was the last time Deryk emailed me")
    assert parsed.script_dir == "examples/google_workspace_brief"
    assert parsed.inputs["task"] == "emails"
    assert parsed.inputs["gmail_query"] == "from:deryk"
    assert parsed.inputs["max_results"] == 1


def test_meetings_monday_date_mapping() -> None:
    parsed = parse_query_to_run("what meetings do I have monday")
    assert parsed.script_dir == "examples/google_workspace_brief"
    assert parsed.inputs["task"] == "meetings"
    assert "date" in parsed.inputs
