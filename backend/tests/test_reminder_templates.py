"""Three deterministic, filled templates per tone; no AI or actual mail."""

import hashlib
import json
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session
from test_ledger import post
from test_reminders import api as api
from test_reminders import mail as mail
from test_reminders import setup

from iou.ledger.models import MutationReceipt
from iou.reminders.templates import TEMPLATES, render


@pytest.mark.parametrize("tone", ["friendly", "playful", "direct"])
def test_all_three_templates_fill_current_names_money_and_items(api, mail, tone):
    friend, _ = setup(api)
    # The template gets its facts from the current ledger, never client-supplied amounts.
    from test_ledger import new_loan

    new_loan(api, friend["id"], "item")
    bodies = []
    for template_id in (1, 2, 3):
        response = post(
            api,
            f"/friends/{friend['id']}/reminder-previews",
            {"tone": tone, "template_id": template_id},
        )
        assert response.status_code == 201, response.text
        body = response.json()["body"]
        assert "Alex" in body and "Owner" in body
        assert "$50.00" in body and "1 borrowed item to return" in body
        assert "Stop IOU reminders:" in body
        assert "{" not in body and "}" not in body
        bodies.append(body)
    assert len(set(bodies)) == 3
    assert not mail.sent


@pytest.mark.parametrize("tone", ["friendly", "playful", "direct"])
def test_money_only_and_item_only_templates_never_invent_obligations(tone):
    assert len(TEMPLATES[tone]) == 3
    for template_id in (1, 2, 3):
        money = render(tone, template_id, "Alex", "Jamie", 1234, 0)
        assert "$12.34" in money and "borrowed item" not in money
        item = render(tone, template_id, "Alex", "Jamie", 0, 2)
        assert "2 borrowed items to return" in item and "$" not in item
        assert "Alex" in item and "Jamie" in item


@pytest.mark.parametrize("template_id", [0, 4, -1, True, "2", 1.5, None])
def test_template_ids_are_strict_and_bounded(api, mail, template_id):
    friend, _ = setup(api)
    assert (
        post(
            api,
            f"/friends/{friend['id']}/reminder-previews",
            {"tone": "friendly", "template_id": template_id},
        ).status_code
        == 422
    )
    assert not mail.sent


def test_tone_only_receipts_replay_default_template_but_not_a_different_choice(api, mail):
    friend, _ = setup(api)
    key = uuid4()
    first = post(api, f"/friends/{friend['id']}/reminder-previews", {"tone": "friendly"}, key)
    legacy = hashlib.sha256(
        json.dumps(
            {"operation": f"reminder-preview:{friend['id']}", "body": {"tone": "friendly"}},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    with Session(api.engine) as session:
        session.get(MutationReceipt, (api.user.id, key)).request_hash = legacy
        session.commit()
    replay = post(
        api,
        f"/friends/{friend['id']}/reminder-previews",
        {"tone": "friendly", "template_id": 1},
        key,
    )
    assert replay.json() == first.json()
    assert replay.headers["idempotency-replayed"] == "true"
    assert (
        post(
            api,
            f"/friends/{friend['id']}/reminder-previews",
            {"tone": "friendly", "template_id": 2},
            key,
        ).status_code
        == 409
    )
    assert not mail.sent
