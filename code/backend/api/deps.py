from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.models import HouseholdMember, User
from app.services import auth, household

DB = Annotated[Session, Depends(get_db)]


def get_session_token(request: Request) -> str | None:
    return request.cookies.get(get_settings().session_cookie_name)


SessionToken = Annotated[str | None, Depends(get_session_token)]


def get_optional_user(db: DB, token: SessionToken) -> User | None:
    return auth.get_session_user(db, token) if token else None


OptionalUser = Annotated[User | None, Depends(get_optional_user)]


def get_current_user(user: OptionalUser) -> User:
    """The logged-in account. Always requires a session, even with AUTH_ENABLED=false."""
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_member(db: DB, user: OptionalUser) -> HouseholdMember:
    """The household member the request acts as.

    With AUTH_ENABLED=false there is no login: the oldest member of the oldest
    household is used.
    """
    if get_settings().auth_enabled:
        if user is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
        member = household.member_for_user(user)
    else:
        member = household.default_member(db)
    if member is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No household yet")
    return member


CurrentMember = Annotated[HouseholdMember, Depends(get_current_member)]
