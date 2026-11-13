import uuid
from typing import TYPE_CHECKING

from sqlalchemy import LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.common import TimestampMixin

if TYPE_CHECKING:
    from app.models.auth.passkey import Passkey
    from app.models.household.member import HouseholdMember


class User(TimestampMixin, Base):
    """A login account. Households are joined via `memberships`."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    # Random WebAuthn "user handle" – deliberately not the internal ID.
    webauthn_user_id: Mapped[bytes] = mapped_column(LargeBinary(64), unique=True)

    memberships: Mapped[list[HouseholdMember]] = relationship(
        back_populates="user", order_by="HouseholdMember.created_at"
    )
    passkeys: Mapped[list[Passkey]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="Passkey.created_at"
    )
