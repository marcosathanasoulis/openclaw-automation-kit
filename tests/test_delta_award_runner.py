from library.delta_award import runner


def test_goal_requires_award_flexible_dates_and_miles_results():
    goal = runner._goal(
        {
            "from": "SFO",
            "to": ["LHR"],
            "days_ahead": 30,
            "travelers": 2,
            "cabin": "business",
            "max_miles": 500000,
        }
    )

    assert "Shop with Miles' MUST be checked" in goal
    assert "My Dates are Flexible' MUST be checked" in goal
    assert "Best Fares For' MUST be 'Delta One'" in goal
    assert "click the 'Miles' tab" in goal
    assert "Do not accept a cash-price page as success." in goal
