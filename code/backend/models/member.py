import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.common import TimestampMixin, pg_enum
from app.models.household.enums import Role

if TYPE_CHECKING:
    from app.models.household.household import Household
    from app.models.household.user import User


class HouseholdMember(TimestampMixin, Base):
    """A person in a household.

    Members exist on their own; an account (`user`) is linked once the person
    accepts an invitation. One account can be a member of several households.
    """

    __tablename__ = "household_members"
    __table_args__ = (
        UniqueConstraint("household_id", "display_name"),
        UniqueConstraint("household_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    display_name: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    # Stored for later; permissions are not enforced yet.
    role: Mapped[Role] = mapped_column(pg_enum(Role, "role"), default=Role.MEMBER)

    household: Mapped[Household] = relationship(back_populates="members")
    user: Mapped[User | None] = relationship(back_populates="memberships")

    @property
    def has_account(self) -> bool:
        return self.user_id is not None
