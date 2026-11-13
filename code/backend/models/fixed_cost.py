import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.common import TimestampMixin


class FixedCost(TimestampMixin, Base):
    """A monthly cost that one member (the payer) transfers for everyone.

    The other members owe the payer their share every month and confirm their
    transfer per month (`FixedCostPayment`).
    """

    __tablename__ = "fixed_costs"
    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("extract(day from start_month) = 1", name="start_month_first_day"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(100))
    amount_cents: Mapped[int]
    payer_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="RESTRICT")
    )
    # First month the cost is due (always the 1st of a month)
    start_month: Mapped[date] = mapped_column(Date)

    shares: Mapped[list[FixedCostShare]] = relationship(
        back_populates="fixed_cost", cascade="all, delete-orphan", lazy="selectin"
    )
    payments: Mapped[list[FixedCostPayment]] = relationship(
        back_populates="fixed_cost", cascade="all, delete-orphan", lazy="selectin"
    )


class FixedCostShare(Base):
    """How much of the monthly amount a member bears (the payer's own share included)."""

    __tablename__ = "fixed_cost_shares"
    __table_args__ = (CheckConstraint("amount_cents > 0", name="amount_positive"),)

    fixed_cost_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixed_costs.id", ondelete="CASCADE"), primary_key=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="RESTRICT"), primary_key=True
    )
    amount_cents: Mapped[int]

    fixed_cost: Mapped[FixedCost] = relationship(back_populates="shares")


class FixedCostPayment(Base):
    """A member confirmed transferring their share to the payer for one month."""

    __tablename__ = "fixed_cost_payments"
    __table_args__ = (UniqueConstraint("fixed_cost_id", "member_id", "month"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    fixed_cost_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("fixed_costs.id", ondelete="CASCADE"), index=True
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_members.id", ondelete="CASCADE")
    )
    month: Mapped[date] = mapped_column(Date)
    # Amount at the time of confirmation, so later price changes keep history intact
    amount_cents: Mapped[int]
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    confirmed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_members.id", ondelete="SET NULL")
    )

    fixed_cost: Mapped[FixedCost] = relationship(back_populates="payments")
