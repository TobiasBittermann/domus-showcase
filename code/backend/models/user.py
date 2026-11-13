import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.common import TimestampMixin, pg_enum
from app.models.household.enums import Role

if TYPE_CHECKING:
    from app.models.auth.passkey import Passkey
    from app.models.household.household import Household


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    household_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("households.id", ondelete="CASCADE"), index=True
    )
    username: Mapped[str] = mapped_column(String(50), unique=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(pg_enum(Role, "role"), default=Role.MEMBER)
    # Random WebAuthn "user handle" – deliberately not the internal ID.
    webauthn_user_id: Mapped[bytes] = mapped_column(LargeBinary(64), unique=True)

    household: Mapped[Household] = relationship(back_populates="members")
    passkeys: Mapped[list[Passkey]] = relationship(
        back_populates="user", cascade="all, delete-orphan", order_by="Passkey.created_at"
    )
