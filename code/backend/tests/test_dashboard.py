import uuid
from datetime import date

import pytest

from app.core.config import get_settings
from app.services.dashboard import add_months, minimal_transfers, split_evenly
from app.services.fixed_costs import current_month


@pytest.fixture(autouse=True)
def _auth_disabled(monkeypatch):
    monkeypatch.setattr(get_settings(), "auth_enabled", False)


@pytest.fixture
def members(client) -> dict[str, str]:
    client.post("/api/households", json={"name": "WG", "display_name": "U1"})
    client.post("/api/household/members", json={"display_name": "U2"})
    return {m["display_name"]: m["id"] for m in client.get("/api/household").json()["members"]}


@pytest.fixture
def stores(client, members) -> dict[str, str]:
    return {
        name: client.post("/api/stores", json={"name": name}).json()["id"]
        for name in ("Rewe", "Aldi")
    }


def expense(client, store_id, buyer_id, amount, day=None, shares=()):
    r = client.post(
        "/api/expenses",
        json={
            "store_id": store_id,
            "buyer_id": buyer_id,
            "amount_cents": amount,
            "booking_date": str(day or date.today()),
            "shares": [{"member_id": m, "amount_cents": a} for m, a in shares],
        },
    )
    assert r.status_code == 201, r.text


def transfers(client) -> list[tuple[str, str, int]]:
    return [
        (t["from_member_id"], t["to_member_id"], t["amount_cents"])
        for t in client.get("/api/dashboard").json()["transfers"]
    ]


def test_helpers():
    assert split_evenly(700, 2) == [350, 350]
    assert split_evenly(701, 2) == [351, 350]
    assert add_months(date(2026, 1, 1), -2) == date(2025, 11, 1)
    assert add_months(date(2026, 12, 1), 1) == date(2027, 1, 1)

    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    result = minimal_transfers({a: 1000, b: -400, c: -600})
    assert {(t.from_member_id, t.to_member_id, t.amount_cents) for t in result} == {
        (c, a, 600),
        (b, a, 400),
    }


def test_example_from_the_receipt(client, members, stores):
    # 20 € at Rewe, bought by U1: U1 3 €, U2 10 €, 7 € shared → U2 owes 13,50 €
    expense(
        client,
        stores["Rewe"],
        members["U1"],
        2000,
        shares=[(members["U1"], 300), (members["U2"], 1000)],
    )
    assert transfers(client) == [(members["U2"], members["U1"], 1350)]


def test_settlement_clears_the_debt(client, members, stores):
    expense(client, stores["Rewe"], members["U1"], 2000)
    assert transfers(client) == [(members["U2"], members["U1"], 1000)]

    r = client.post(
        "/api/settlements",
        json={
            "from_member_id": members["U2"],
            "to_member_id": members["U1"],
            "amount_cents": 1000,
        },
    )
    assert r.status_code == 201, r.text
    assert transfers(client) == []

    same = {"from_member_id": members["U1"], "to_member_id": members["U1"], "amount_cents": 1}
    assert client.post("/api/settlements", json=same).status_code == 422


def test_members_joining_later_do_not_share_older_expenses(client, members, stores):
    expense(client, stores["Rewe"], members["U1"], 1000)
    u3 = client.post("/api/household/members", json={"display_name": "U3"}).json()["id"]
    # U3 joined afterwards: the 10 € are split between U1 and U2 only
    assert transfers(client) == [(members["U2"], members["U1"], 500)]
    assert all(t[0] != u3 for t in transfers(client))


def test_figures_and_store_slices(client, members, stores):
    this_month = current_month()
    last_month = add_months(this_month, -1)
    long_ago = add_months(this_month, -3)
    expense(client, stores["Rewe"], members["U1"], 2000, this_month)
    expense(client, stores["Rewe"], members["U2"], 1000, this_month)
    expense(client, stores["Aldi"], members["U1"], 500, this_month)
    expense(client, stores["Aldi"], members["U1"], 800, last_month)
    expense(client, stores["Aldi"], members["U1"], 9900, long_ago)  # outside the 3 months

    d = client.get("/api/dashboard").json()
    assert d["month"] == str(this_month)
    assert d["month_total_cents"] == 3500
    assert d["previous_month_total_cents"] == 800
    assert d["month_purchase_count"] == 3
    assert [(s["name"], s["amount_cents"], s["count"]) for s in d["month_by_store"]] == [
        ("Rewe", 3000, 2),
        ("Aldi", 500, 1),
    ]
    assert d["recent_from"] == str(add_months(this_month, -2))
    assert [(s["name"], s["count"]) for s in d["recent_by_store"]] == [("Rewe", 2), ("Aldi", 2)]


def test_fixed_cost_debts(client, members):
    client.post(
        "/api/fixed-costs",
        json={
            "name": "Miete",
            "amount_cents": 80000,
            "payer_id": members["U1"],
            "start_month": str(add_months(current_month(), -1)),
            "shares": [
                {"member_id": members["U1"], "amount_cents": 40000},
                {"member_id": members["U2"], "amount_cents": 40000},
            ],
        },
    )
    d = client.get("/api/dashboard").json()
    assert d["fixed_costs_monthly_cents"] == 80000
    assert d["fixed_cost_debts"] == [
        {
            "from_member_id": members["U2"],
            "to_member_id": members["U1"],
            "amount_cents": 80000,
            "open_count": 2,
        }
    ]
    # Fixed costs are settled via payment confirmations, not shopping transfers
    assert d["transfers"] == []


def test_paid_and_total_costs_per_member(client, members, stores):
    this_month = current_month()
    # U1 pays 20 € (U1 3 €, U2 10 €, 7 € shared), U2 pays 5 € shared; last month is ignored
    expense(
        client,
        stores["Rewe"],
        members["U1"],
        2000,
        this_month,
        shares=[(members["U1"], 300), (members["U2"], 1000)],
    )
    expense(client, stores["Aldi"], members["U2"], 500, this_month)
    expense(client, stores["Aldi"], members["U2"], 9999, add_months(this_month, -1))
    client.post(
        "/api/fixed-costs",
        json={
            "name": "Internet",
            "amount_cents": 4000,
            "payer_id": members["U1"],
            "start_month": str(this_month),
            "shares": [
                {"member_id": members["U1"], "amount_cents": 1000},
                {"member_id": members["U2"], "amount_cents": 3000},
            ],
        },
    )

    rows = {r["member_id"]: r for r in client.get("/api/dashboard").json()["members"]}
    assert rows[members["U1"]] == {
        "member_id": members["U1"],
        "paid_cents": 2000,
        "shopping_cents": 300 + 350 + 250,
        "fixed_cents": 1000,
        "total_cents": 1900,
    }
    assert rows[members["U2"]] == {
        "member_id": members["U2"],
        "paid_cents": 500,
        "shopping_cents": 1000 + 350 + 250,
        "fixed_cents": 3000,
        "total_cents": 4600,
    }
