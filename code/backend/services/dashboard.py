"""Balances between members and figures for the start page."""

import uuid
from collections import defaultdict
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Expense, Household, HouseholdMember, Settlement, Store
from app.schemas import (
    DashboardOut,
    FixedCostDebtOut,
    MemberMonthOut,
    SettlementIn,
    StoreSliceOut,
    TransferOut,
)
from app.services import fixed_costs


class SettlementError(ValueError):
    pass


def split_evenly(cents: int, parts: int) -> list[int]:
    """Split into `parts` amounts that differ by at most one cent (first ones get more)."""
    base, remainder = divmod(cents, parts)
    return [base + (1 if i < remainder else 0) for i in range(parts)]


def add_months(month: date, delta: int) -> date:
    index = month.year * 12 + month.month - 1 + delta
    return date(index // 12, index % 12 + 1, 1)


# --- Balances -------------------------------------------------------------------


def balances(db: Session, household: Household) -> dict[uuid.UUID, int]:
    """Shopping balance per member: positive = others owe them, negative = they owe.

    The shared part of an expense is split among the members who already belonged
    to the household when it was entered, so joining later does not inherit old costs.
    """
    members = list(household.members)
    balance = {m.id: 0 for m in members}

    expenses = db.scalars(select(Expense).where(Expense.household_id == household.id))
    for expense in expenses:
        balance[expense.buyer_id] += expense.amount_cents
        for member_id, cents in consumption(expense, members).items():
            balance[member_id] -= cents

    settlements = db.scalars(select(Settlement).where(Settlement.household_id == household.id))
    for s in settlements:
        balance[s.from_member_id] += s.amount_cents
        balance[s.to_member_id] -= s.amount_cents
    return balance


def consumption(expense: Expense, members: list[HouseholdMember]) -> dict[uuid.UUID, int]:
    """Each member's share of an expense: personal share plus part of the shared amount."""
    result: dict[uuid.UUID, int] = defaultdict(int)
    for share in expense.shares:
        result[share.member_id] += share.amount_cents
    participants = [m for m in members if m.created_at <= expense.created_at] or members
    for member, part in zip(
        participants, split_evenly(expense.shared_cents, len(participants)), strict=True
    ):
        result[member.id] += part
    return result


def minimal_transfers(balance: dict[uuid.UUID, int]) -> list[TransferOut]:
    """Greedy settlement: the largest debtor pays the largest creditor, and so on."""
    debtors = sorted(([m, -b] for m, b in balance.items() if b < 0), key=lambda x: -x[1])
    creditors = sorted(([m, b] for m, b in balance.items() if b > 0), key=lambda x: -x[1])
    transfers = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        amount = min(debtors[i][1], creditors[j][1])
        transfers.append(
            TransferOut(
                from_member_id=debtors[i][0], to_member_id=creditors[j][0], amount_cents=amount
            )
        )
        debtors[i][1] -= amount
        creditors[j][1] -= amount
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return transfers


def create_settlement(
    db: Session, member: HouseholdMember, data: SettlementIn, today: date | None = None
) -> Settlement:
    member_ids = {m.id for m in member.household.members}
    if data.from_member_id not in member_ids or data.to_member_id not in member_ids:
        raise SettlementError("Settlement refers to a non-member")
    settlement = Settlement(
        household_id=member.household_id,
        from_member_id=data.from_member_id,
        to_member_id=data.to_member_id,
        amount_cents=data.amount_cents,
        settled_on=today or date.today(),
        created_by_id=member.id,
    )
    db.add(settlement)
    db.commit()
    return settlement


# --- Dashboard -------------------------------------------------------------------


def _by_store(db: Session, household: Household, start: date, end: date) -> list[StoreSliceOut]:
    """Spending per store with booking date in [start, end), largest first."""
    rows = db.execute(
        select(
            Store.id,
            Store.name,
            func.sum(Expense.amount_cents),
            func.count(Expense.id),
        )
        .join(Expense.store)
        .where(
            Expense.household_id == household.id,
            Expense.booking_date >= start,
            Expense.booking_date < end,
        )
        .group_by(Store.id, Store.name)
        .order_by(func.sum(Expense.amount_cents).desc(), Store.name)
    )
    return [
        StoreSliceOut(store_id=sid, name=name, amount_cents=int(total), count=count)
        for sid, name, total, count in rows
    ]


def _fixed_cost_debts(db: Session, household: Household) -> list[FixedCostDebtOut]:
    totals: dict[tuple[uuid.UUID, uuid.UUID], list[int]] = defaultdict(lambda: [0, 0])
    for due in fixed_costs.open_dues(db, household):
        entry = totals[(due.member_id, due.fixed_cost.payer_id)]
        entry[0] += due.amount_cents
        entry[1] += 1
    return [
        FixedCostDebtOut(
            from_member_id=debtor, to_member_id=payer, amount_cents=amount, open_count=count
        )
        for (debtor, payer), (amount, count) in totals.items()
    ]


def _member_month(
    db: Session, household: Household, month: date, next_month: date
) -> list[MemberMonthOut]:
    members = list(household.members)
    paid = {m.id: 0 for m in members}
    shopping = {m.id: 0 for m in members}
    fixed = {m.id: 0 for m in members}

    expenses = db.scalars(
        select(Expense).where(
            Expense.household_id == household.id,
            Expense.booking_date >= month,
            Expense.booking_date < next_month,
        )
    )
    for expense in expenses:
        paid[expense.buyer_id] += expense.amount_cents
        for member_id, cents in consumption(expense, members).items():
            shopping[member_id] += cents

    for fc in fixed_costs.list_fixed_costs(db, household):
        if fc.start_month <= month:
            for share in fc.shares:
                fixed[share.member_id] += share.amount_cents

    return [
        MemberMonthOut(
            member_id=m.id,
            paid_cents=paid[m.id],
            shopping_cents=shopping[m.id],
            fixed_cents=fixed[m.id],
            total_cents=shopping[m.id] + fixed[m.id],
        )
        for m in members
    ]


def dashboard(db: Session, household: Household, today: date | None = None) -> DashboardOut:
    month = fixed_costs.current_month(today)
    next_month = add_months(month, 1)
    previous_month = add_months(month, -1)
    recent_from = add_months(month, -2)

    month_by_store = _by_store(db, household, month, next_month)
    previous = _by_store(db, household, previous_month, month)
    monthly_fixed = sum(
        fc.amount_cents
        for fc in fixed_costs.list_fixed_costs(db, household)
        if fc.start_month <= month
    )
    return DashboardOut(
        transfers=minimal_transfers(balances(db, household)),
        fixed_cost_debts=_fixed_cost_debts(db, household),
        month=month,
        month_total_cents=sum(s.amount_cents for s in month_by_store),
        previous_month_total_cents=sum(s.amount_cents for s in previous),
        month_purchase_count=sum(s.count for s in month_by_store),
        month_by_store=month_by_store,
        recent_from=recent_from,
        recent_by_store=_by_store(db, household, recent_from, next_month),
        fixed_costs_monthly_cents=monthly_fixed,
        members=_member_month(db, household, month, next_month),
    )
