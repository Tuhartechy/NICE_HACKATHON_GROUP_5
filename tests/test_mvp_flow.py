"""Critical cross-feature acceptance tests on a freshly seeded database."""
import importlib
from datetime import date

import pytest

AS_OF = date(2026, 9, 1)


@pytest.fixture()
def seeded(tmp_path, monkeypatch):
    from mednexa import config
    from mednexa.db import seed
    path = tmp_path / "mx.db"
    seed.build(path, validate=False)
    monkeypatch.setattr(config, "DB_PATH", path)
    return path


def test_segmentation_boundaries():
    from mednexa.services.segmentation import segment_of, visits_per_month
    assert [segment_of(x) for x in (0, 69, 70, 149, 150, 305)] == ["C", "C", "B", "B", "A", "A"]
    assert (visits_per_month("A"), visits_per_month("B"), visits_per_month("C")) == (4, 2, 1)


def test_r004_acceptance_plan(seeded):
    from mednexa.services import plans
    plans.generate("R004", AS_OF, 6, AS_OF, "test")
    items = plans.list_items("R004", AS_OF)
    day1 = set(items[items.planned_date == "2026-09-01"].doctor_id)
    assert "D068" in day1
    assert {"D076", "D078", "D080"} <= set(items.doctor_id)
    assert items.groupby("planned_date").size().max() <= 5
    assert items.doctor_id.is_unique                                   # D068's 4 follow-ups merged
    d068 = items[items.doctor_id == "D068"].iloc[0]
    assert len(d068.follow_up_ids.split(",")) == 4
    # deterministic regeneration
    before = list(zip(items.doctor_id, items.planned_date))
    plans.generate("R004", AS_OF, 6, AS_OF, "test")
    again = plans.list_items("R004", AS_OF)
    assert list(zip(again.doctor_id, again.planned_date)) == before


def test_capacity_overflow_for_rep_with_many_overdue(seeded):
    from mednexa.services import plans
    plans.generate("R005", AS_OF, 6, AS_OF, "test")
    items = plans.list_items("R005", AS_OF)
    assert items.groupby("planned_date").size().max() <= 5
    assert any("Capacity overflow" in " ".join(r) for r in items.reasons_list)


def test_log_visit_rolls_back_on_insufficient_stock(seeded):
    from mednexa.core.errors import ConflictError
    from mednexa.services import inventory, visits
    before = inventory.stock().set_index("product_id").current_stock.to_dict()
    with pytest.raises(ConflictError):
        visits.log_visit({"rep_id": "R004", "doctor_id": "D068", "visit_date": AS_OF, "outcome": "Positive",
                          "products": [{"product_id": "P004", "feedback": None}], "issued": {"P004": 999}},
                         as_of=AS_OF, actor="test")
    assert inventory.stock().set_index("product_id").current_stock.to_dict() == before
    assert len(visits.history()) == 320


def test_rejects_invalid_visits(seeded):
    from mednexa.core.errors import ValidationError
    from mednexa.services import visits
    base = {"rep_id": "R004", "doctor_id": "D068", "visit_date": AS_OF, "outcome": "Positive",
            "products": [{"product_id": "P001"}]}
    for bad in ({"visit_date": date(2026, 9, 2)}, {"visit_date": date(2026, 8, 30)}, {"outcome": None},
                {"products": []}, {"doctor_id": "D001"}):
        with pytest.raises(ValidationError):
            visits.log_visit({**base, **bad}, as_of=AS_OF, actor="test")


def test_end_to_end_followup_action_loop(seeded):
    from mednexa.services import actions, analytics, inventory, plans, visits
    plans.generate("R004", AS_OF, 6, AS_OF, "test")
    item = plans.list_items("R004", AS_OF).query("doctor_id == 'D068'").iloc[0]
    open_before = actions.open_actions(AS_OF, "R004")
    assert (open_before.doctor_id == "D068").sum() >= 4
    stock_before = inventory.stock().set_index("product_id").loc["P004", "current_stock"]
    vid = visits.log_visit({"rep_id": "R004", "doctor_id": "D068", "visit_date": AS_OF, "outcome": "Positive",
                            "products": [{"product_id": "P004", "feedback": "Positive"}], "issued": {"P004": 5},
                            "close_follow_up_ids": item.follow_up_ids.split(","),
                            "new_follow_up": {"due_date": date(2026, 9, 8)}, "plan_item_id": item.plan_item_id},
                           as_of=AS_OF, actor="test")
    assert vid == "V0321"
    assert inventory.stock().set_index("product_id").loc["P004", "current_stock"] == stock_before - 5
    assert plans.list_items("R004", AS_OF).set_index("plan_item_id").loc[item.plan_item_id, "status"] == "COMPLETED"
    after = actions.open_actions(AS_OF, "R004")
    assert not ((after.doctor_id == "D068") & (after.action_type == "OVERDUE_FOLLOW_UP")).any()
    s, e = analytics.default_period(AS_OF)
    k = analytics.kpis(analytics.Filters(s, e), AS_OF)
    assert k["overdue_fu"] == 22 and k["visits"] == 321 and k["plan_completion"] == 1.0
    assert inventory.stock().ledger_ok.all()


def test_contact_completion_needs_note_and_updates_feature3(seeded):
    from mednexa.core.errors import ValidationError
    from mednexa.services import actions, followups
    df = actions.open_actions(AS_OF, "R005")
    key = df[df.action_type == "OVERDUE_FOLLOW_UP"].action_key.iloc[0]
    with pytest.raises(ValidationError):
        actions.complete_followup_by_contact(key, " ", AS_OF, "test")
    actions.complete_followup_by_contact(key, "Called the clinic", AS_OF, "test")
    fu = followups.list_followups(AS_OF, rep_id="R005").set_index("follow_up_id").loc[key.split(":")[1]]
    assert fu.status == "Completed" and fu.completion_method == "CONTACT"
    assert key not in set(actions.open_actions(AS_OF, "R005").action_key)


def test_missed_visits_appear_when_business_date_moves(seeded):
    from mednexa.services import actions, plans
    plans.generate("R004", AS_OF, 6, AS_OF, "test")
    s = actions.summary(actions.open_actions(date(2026, 9, 3), "R004"))
    assert s["missed"] > 0
    first = actions.open_actions(date(2026, 9, 3), "R004")
    again = actions.open_actions(date(2026, 9, 3), "R004")
    assert list(first.action_key) == list(again.action_key)          # deterministic, no duplicates
    assert first.action_key.is_unique
