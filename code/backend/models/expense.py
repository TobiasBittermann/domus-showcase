import uuid
from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:
    from app.models.expenses.store import Store


class Expense(TimestampMixin, Base):
    """One receipt. Whatever is not a personal share is split among all members."""

    __tablename__ = "expenses"
    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_positive"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    store_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("stores.id", ondelete="RESTRICT"))
    buyer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="RESTRICT")
    )
    amount_cents: Mapped[int]
    booking_date: Mapped[date] = mapped_column(Date, index=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )

    store: Mapped[Store] = relationship(lazy="joined")
    shares: Mapped[list[ExpenseShare]] = relationship(
        back_populates="expense", cascade="all, delete-orphan", lazy="selectin"
    )

    @property
    def shared_cents(self) -> int:
        return self.amount_cents - sum(s.amount_cents for s in self.shares)


class ExpenseShare(Base):
    """Part of an expense that belongs to a single member."""

    __tablename__ = "expense_shares"
    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_positive"),)

    expense_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("expenses.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="RESTRICT"), primary_key=True
    )
    amount_cents: Mapped[int]

    expense: Mapped[Expense] = relationship(back_populates="shares")
