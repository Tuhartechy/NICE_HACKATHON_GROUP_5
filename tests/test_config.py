import re
from datetime import date

from mednexa import config


def test_approved_segmentation_rules():
    assert config.SEGMENT_RULES == (("A", 150, 4, "High potential"),
                                    ("B", 70, 2, "Medium potential"),
                                    ("C", 0, 1, "Lower potential"))
    floors = [r[1] for r in config.SEGMENT_RULES]
    assert floors == sorted(floors, reverse=True) and floors[-1] == 0


def test_business_date_and_calendar():
    assert config.DEFAULT_AS_OF == date(2026, 9, 1)
    assert config.BUSINESS_DATE_MIN <= config.DEFAULT_AS_OF <= config.BUSINESS_DATE_MAX
    assert config.WORKING_WEEKDAYS == frozenset({0, 1, 2, 3, 4, 5})


def test_approved_value_sets():
    assert config.OUTCOMES == ("Positive", "Neutral", "Negative", "Doctor unavailable")
    assert config.FEEDBACK == ("Positive", "Neutral", "Negative")
    assert config.NOT_RECORDED == "Not recorded"
    assert config.COMPLETION_METHODS == ("VISIT", "CONTACT")


def test_approved_defaults():
    assert config.OVERDUE_CRITICAL_DAYS == 14
    assert config.UPCOMING_WINDOW_DAYS == 7
    assert config.PREP_WINDOW_WORKING_DAYS == 1
    assert config.RX_SCORE_CAP == 300
    assert config.PLAN_DEFAULT_DAYS == 6
    assert config.STOCK_WATCH_RATIO == 1.5
    assert config.PLAN_DAILY_CAPACITY == 5


def test_planning_weights_sum_to_one():
    assert abs(sum(config.PLAN_WEIGHTS.values()) - 1.0) < 1e-9
    assert dict(config.PLAN_WEIGHTS) == {"urgency": .40, "recency": .25, "potential": .25, "never": .10}


def test_theme_tokens_are_brand_colours():
    hexes = re.compile(r"^#[0-9A-Fa-f]{6}$")
    assert all(hexes.match(v) for v in config.THEME.values())
    assert config.THEME["bg"] == "#111827" and config.THEME["primary"] == "#0F766E"
    assert config.THEME["accent"] == "#B8E35A" and config.THEME["surface"] == "#1B2433"
    assert config.THEME["text"] == "#F5F5F0"


def test_config_is_immutable_where_it_matters():
    import pytest
    with pytest.raises(TypeError):
        config.PLAN_WEIGHTS["urgency"] = 1.0  # type: ignore[index]
    with pytest.raises(TypeError):
        config.THEME["bg"] = "#000000"  # type: ignore[index]
