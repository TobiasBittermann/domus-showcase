"""Recurring monthly costs: who owes the payer what, and confirmed transfers."""

import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FixedCost, FixedCostPayment, FixedCostShare, Household, HouseholdMember
from app.schemas import FixedCostIn


class FixedCostError(ValueError):
    """Request refers to data outside the household or to an impossible payment."""


class AlreadyConfirmedError(ValueError):
    pass


@dataclass(frozen=True)
class Due:
    fixed_cost: FixedCost
    member_id: uuid.UUID
    month: date
    amount_cents: int
    payment: FixedCostPayment | None


def current_month(today: date | None = None) -> date:
    return (today or date.today()).replace(day=1)


def _months(start: date, end: date) -> Iterator[date]:
    month = start
    while month <= end:
        yield month
        month = month.replace(year=month.year + month.month // 12, month=month.month % 12 + 1)


# --- Fixed costs ---------------------------------------------------------------


def list_fixed_costs(db: Session, household: Household) -> list[FixedCost]:
    stmt = (
        select(FixedCost)
        .where(FixedCost.household_id == household.id)
        .order_by(FixedCost.created_at)
    )
    return list(db.scalars(stmt))


def get_fixed_cost(db: Session, household: Household, fixed_cost_id: uuid.UUID) -> FixedCost:
    fixed_cost = db.get(FixedCost, fixed_cost_id)
    if fixed_cost is None or fixed_cost.household_id != household.id:
        raise LookupError("Fixed cost not found")
    return fixed_cost


def _check_members(household: Household, data: FixedCostIn) -> None:
    member_ids = {m.id for m in household.members}
    if data.payer_id not in member_ids:
        raise FixedCostError("Payer is not a member of this household")
    if any(s.member_id not in member_ids for s in data.shares):
        raise FixedCostError("Share refers to a non-member")


def create_fixed_cost(db: Session, household: Household, data: FixedCostIn) -> FixedCost:
    _check_members(household, data)
    fixed_cost = FixedCost(household_id=household.id)
    _apply(fixed_cost, data)
    db.add(fixed_cost)
    db.commit()
    return fixed_cost


def update_fixed_cost(db: Session, fixed_cost: FixedCost, data: FixedCostIn) -> FixedCost:
    """Changes apply to all open months; confirmed months keep their amount."""
    household = db.get_one(Household, fixed_cost.household_id)
    _check_members(household, data)
    fixed_cost.shares.clear()
    db.flush()
    _apply(fixed_cost, data)
    db.commit()
    return fixed_cost


def _apply(fixed_cost: FixedCost, data: FixedCostIn) -> None:
    fixed_cost.name = data.name.strip()
    fixed_cost.amount_cents = data.amount_cents
    fixed_cost.payer_id = data.payer_id
    fixed_cost.start_month = data.start_month
    fixed_cost.shares = [
        FixedCostShare(member_id=s.member_id, amount_cents=s.amount_cents) for s in data.shares
    ]


def delete_fixed_cost(db: Session, fixed_cost: FixedCost) -> None:
    db.delete(fixed_cost)
    db.commit()


# --- Dues and payments ---------------------------------------------------------


def _dues(fixed_cost: FixedCost, months: Iterator[date] | list[date]) -> Iterator[Due]:
    payments = {(p.member_id, p.month): p for p in fixed_cost.payments}
    for month in months:
        if month < fixed_cost.start_month:
            continue
        for share in fixed_cost.shares:
            # The payer transfers the whole amount and owes nobody
            if share.member_id == fixed_cost.payer_id:
                continue
            payment = payments.get((share.member_id, month))
            amount = payment.amount_cents if payment else share.amount_cents
            yield Due(fixed_cost, share.member_id, month, amount, payment)


def dues_for_month(db: Session, household: Household, month: date) -> list[Due]:
    return [d for fc in list_fixed_costs(db, household) for d in _dues(fc, [month])]


def open_dues(db: Session, household: Household, until: date | None = None) -> list[Due]:
    """All unconfirmed dues up to and including `until` (default: current month)."""
    until = until or current_month()
    dues = [
        d
        for fc in list_fixed_costs(db, household)
        for d in _dues(fc, _months(fc.start_month, until))
        if d.payment is None
    ]
    return sorted(dues, key=lambda d: (d.month, d.fixed_cost.name))


def confirm_payment(
    db: Session,
    fixed_cost: FixedCost,
    member_id: uuid.UUID,
    month: date,
    confirmed_by: HouseholdMember | None,
) -> Due:
    month = month.replace(day=1)
    if month < fixed_cost.start_month:
        raise FixedCostError("The fixed cost is not due in this month yet")
    if member_id == fixed_cost.payer_id:
        raise FixedCostError("The payer does not owe anything")
    share = next((s for s in fixed_cost.shares if s.member_id == member_id), None)
    if share is None:
        raise FixedCostError("This member has no share in the fixed cost")
    if any(p.member_id == member_id and p.month == month for p in fixed_cost.payments):
        raise AlreadyConfirmedError("Payment is already confirmed")

    payment = FixedCostPayment(
        member_id=member_id,
        month=month,
        amount_cents=share.amount_cents,
        confirmed_by_id=confirmed_by.id if confirmed_by else None,
    )
    fixed_cost.payments.append(payment)
    db.commit()
    db.refresh(payment)
    return Due(fixed_cost, member_id, month, payment.amount_cents, payment)


def revoke_payment(db: Session, fixed_cost: FixedCost, member_id: uuid.UUID, month: date) -> None:
    payment = next(
        (p for p in fixed_cost.payments if p.member_id == member_id and p.month == month), None
    )
    if payment is None:
        raise LookupError("Payment not found")
    fixed_cost.payments.remove(payment)
    db.commit()
