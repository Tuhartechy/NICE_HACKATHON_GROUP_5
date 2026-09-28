import plotly.io as pio

from mednexa import config
from mednexa.ui import components as ui
from mednexa.ui import formatting as fmt
from mednexa.ui import theme


def test_all_text_is_escaped():
    html = ui.page_header_html("<script>x</script>", "a & b", stage="Act", feature="F<5>")
    assert "<script>" not in html and "&lt;script&gt;" in html and "a &amp; b" in html


def test_segment_badges():
    for seg in "ABC":
        assert f"mx-seg-{seg}" in ui.segment_badge_html(seg)
    assert "?" in ui.segment_badge_html("Z")


def test_kpi_tile_delta_and_tone():
    html = ui.kpi_tile_html(ui.Kpi("Visits", "320", foot="August", tone="accent", delta="+12", delta_direction="up"))
    assert "mx-tone-accent" in html and "mx-delta-up" in html and "August" in html
    assert "mx-tone-neutral" in ui.kpi_tile_html(ui.Kpi("X", "1", tone="rainbow"))


def test_action_card_priority_styles():
    card = ui.ActionCardView("CRITICAL", "Overdue follow-up", "Dr. Test", "Cardiologist · Area",
                             "Pending 15 days", "Contact the doctor", "18 Aug 2026", segment="A")
    html = ui.action_card_html(card)
    assert "mx-prio-CRITICAL" in html and "mx-tone-critical" in html and "mx-seg-A" in html
    assert "mx-prio-LOW" in ui.action_card_html(card.__class__(**{**card.__dict__, "priority": "??"}))


def test_states_and_panels():
    assert "mx-state-error" in ui.error_state_html("boom")
    assert "Milestone 3" in ui.milestone_panel_html(3, "Next", ["a"], ["services.doctors"])
    assert ui.flow_strip_html("PLAN").count("mx-current") == 1


def test_formatting_never_fakes_values():
    assert fmt.fmt_pct(None) == "—" and fmt.fmt_pct(0.724) == "72%"
    assert fmt.fmt_int(None) == "—" and fmt.fmt_int(1234) == "1,234"
    assert fmt.or_not_recorded(None) == config.NOT_RECORDED and fmt.or_not_recorded("Positive") == "Positive"
    assert fmt.or_not_recorded(float("nan")) == config.NOT_RECORDED
    assert fmt.fmt_date("2026-09-01") == "01 Sep 2026" and fmt.fmt_signed(3) == "+3"


def test_theme_css_and_plotly_template():
    css = theme.css()
    for token in ("#111827", "#0F766E", "#B8E35A", "#1B2433", "#F5F5F0"):
        assert token in css
    assert "gradient" not in css.lower() and "backdrop-filter" not in css.lower()
    name = theme.register_plotly_template()
    assert name in pio.templates and list(pio.templates[name].layout.colorway) == list(config.CHART_COLORWAY)
