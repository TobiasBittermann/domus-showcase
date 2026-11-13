"""Passkey authentication (WebAuthn), sessions and one-time tokens."""

import uuid
from datetime import timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DBSession
from webauthn import (
    generate_authentication_options,
    generate_registration_options,
    verify_authentication_response,
    verify_registration_response,
)
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    generate_user_handle,
    options_to_json_dict,
)
from webauthn.helpers.exceptions import InvalidAuthenticationResponse, InvalidRegistrationResponse
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    PublicKeyCredentialDescriptor,
    ResidentKeyRequirement,
    UserVerificationRequirement,
)

from app.core.config import get_settings
from app.core.security import generate_token, hash_token, utcnow
from app.models import (
    AuthToken,
    AuthTokenPurpose,
    ChallengePurpose,
    HouseholdMember,
    Passkey,
    Session,
    User,
    WebAuthnChallenge,
)


def _bad_request(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_400_BAD_REQUEST, detail)


# --- Sessions -----------------------------------------------------------------


def create_session(db: DBSession, user: User) -> str:
    settings = get_settings()
    token = generate_token()
    db.add(
        Session(
            token_hash=hash_token(token),
            user_id=user.id,
            expires_at=utcnow() + timedelta(days=settings.session_lifetime_days),
        )
    )
    db.commit()
    return token


def get_session_user(db: DBSession, token: str) -> User | None:
    session = db.scalar(select(Session).where(Session.token_hash == hash_token(token)))
    now = utcnow()
    if session is None or session.expires_at <= now:
        return None

    # Sliding expiration: active sessions are extended at most once per hour.
    if now - session.last_seen_at > timedelta(hours=1):
        session.last_seen_at = now
        session.expires_at = now + timedelta(days=get_settings().session_lifetime_days)
        db.commit()
    return session.user


def delete_session(db: DBSession, token: str) -> None:
    db.execute(delete(Session).where(Session.token_hash == hash_token(token)))
    db.commit()


# --- Invitation and recovery tokens -------------------------------------------


class MemberAlreadyLinkedError(ValueError):
    pass


def create_invite(
    db: DBSession, member: HouseholdMember, created_by: HouseholdMember | None = None
) -> tuple[str, AuthToken]:
    """Invitation link with which a person registers and is linked to `member`."""
    if member.user_id is not None:
        raise MemberAlreadyLinkedError("This member already has an account")
    lifetime = timedelta(hours=get_settings().invite_lifetime_hours)
    return _create_auth_token(
        db,
        AuthToken(
            purpose=AuthTokenPurpose.INVITE,
            member_id=member.id,
            created_by_id=created_by.id if created_by else None,
            expires_at=utcnow() + lifetime,
        ),
    )


def create_recovery(db: DBSession, user: User) -> tuple[str, AuthToken]:
    lifetime = timedelta(hours=get_settings().recovery_lifetime_hours)
    return _create_auth_token(
        db,
        AuthToken(
            purpose=AuthTokenPurpose.RECOVERY,
            user_id=user.id,
            expires_at=utcnow() + lifetime,
        ),
    )


def _create_auth_token(db: DBSession, auth_token: AuthToken) -> tuple[str, AuthToken]:
    token = generate_token()
    auth_token.token_hash = hash_token(token)
    db.add(auth_token)
    db.commit()
    return token, auth_token


def auth_token_url(token: str, auth_token: AuthToken) -> str:
    path = "invite" if auth_token.purpose == AuthTokenPurpose.INVITE else "recover"
    return f"{get_settings().app_url.rstrip('/')}/{path}/{token}"


def get_valid_auth_token(db: DBSession, token: str) -> AuthToken:
    auth_token = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(token)))
    if not _is_usable(auth_token):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Link is invalid or has expired")
    return auth_token


def _is_usable(auth_token: AuthToken | None) -> bool:
    if auth_token is None or auth_token.used_at is not None or auth_token.expires_at <= utcnow():
        return False
    # An invitation is void once its member has been linked to an account otherwise
    return not (auth_token.member is not None and auth_token.member.user_id is not None)


# --- WebAuthn: Challenges -----------------------------------------------------


def _store_challenge(db: DBSession, challenge: WebAuthnChallenge) -> WebAuthnChallenge:
    now = utcnow()
    # Clean up expired challenges along the way
    db.execute(delete(WebAuthnChallenge).where(WebAuthnChallenge.expires_at <= now))
    challenge.expires_at = now + timedelta(seconds=get_settings().challenge_lifetime_seconds)
    db.add(challenge)
    db.commit()
    return challenge


def _consume_challenge(
    db: DBSession, challenge_id: uuid.UUID, purpose: ChallengePurpose
) -> WebAuthnChallenge:
    """Load a challenge and delete it immediately – every challenge is single-use."""
    challenge = db.get(WebAuthnChallenge, challenge_id)
    if challenge is None:
        raise _bad_request("Unknown or already used challenge")
    db.delete(challenge)
    db.commit()
    if challenge.purpose != purpose or challenge.expires_at <= utcnow():
        raise _bad_request("Challenge has expired")
    return challenge


# --- WebAuthn: registration ---------------------------------------------------


def start_registration(
    db: DBSession, token: str, username: str | None, display_name: str | None
) -> tuple[uuid.UUID, dict[str, Any]]:
    """Start a registration via an invitation or recovery link."""
    auth_token = get_valid_auth_token(db, token)

    if auth_token.purpose == AuthTokenPurpose.RECOVERY:
        assert auth_token.user is not None
        return _start_registration_for_user(db, auth_token.user, auth_token)

    if not username or not display_name:
        raise _bad_request("Username and display name are required")
    _ensure_username_free(db, username)
    user_handle = generate_user_handle()
    options = _registration_options(user_handle, username, display_name, exclude=[])
    challenge = _store_challenge(
        db,
        WebAuthnChallenge(
            challenge=options.challenge,
            purpose=ChallengePurpose.REGISTRATION,
            auth_token_id=auth_token.id,
            pending_user={
                "username": username,
                "display_name": display_name,
                "webauthn_user_id": bytes_to_base64url(user_handle),
            },
        ),
    )
    return challenge.id, options_to_json_dict(options)


def start_passkey_addition(db: DBSession, user: User) -> tuple[uuid.UUID, dict[str, Any]]:
    """Logged-in user registers an additional passkey."""
    return _start_registration_for_user(db, user, auth_token=None)


def _start_registration_for_user(
    db: DBSession, user: User, auth_token: AuthToken | None
) -> tuple[uuid.UUID, dict[str, Any]]:
    options = _registration_options(
        user.webauthn_user_id,
        user.username,
        user.display_name,
        exclude=[p.credential_id for p in user.passkeys],
    )
    challenge = _store_challenge(
        db,
        WebAuthnChallenge(
            challenge=options.challenge,
            purpose=ChallengePurpose.REGISTRATION,
            user_id=user.id,
            auth_token_id=auth_token.id if auth_token else None,
        ),
    )
    return challenge.id, options_to_json_dict(options)


def _registration_options(
    user_handle: bytes, username: str, display_name: str, exclude: list[bytes]
):
    settings = get_settings()
    return generate_registration_options(
        rp_id=settings.webauthn_rp_id,
        rp_name=settings.webauthn_rp_name,
        user_id=user_handle,
        user_name=username,
        user_display_name=display_name,
        exclude_credentials=[PublicKeyCredentialDescriptor(id=c) for c in exclude],
        authenticator_selection=AuthenticatorSelectionCriteria(
            # Discoverable credentials: login without entering a username
            resident_key=ResidentKeyRequirement.REQUIRED,
            user_verification=UserVerificationRequirement.REQUIRED,
        ),
    )


def finish_registration(
    db: DBSession,
    challenge_id: uuid.UUID,
    credential: dict[str, Any],
    passkey_name: str,
    current_user: User | None = None,
) -> User:
    challenge = _consume_challenge(db, challenge_id, ChallengePurpose.REGISTRATION)

    auth_token: AuthToken | None = None
    if challenge.auth_token_id is not None:
        auth_token = db.get(AuthToken, challenge.auth_token_id)
        if not _is_usable(auth_token):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Link is invalid or has expired")
    elif current_user is None or challenge.user_id != current_user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Challenge belongs to a different user")

    settings = get_settings()
    try:
        verified = verify_registration_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            require_user_verification=True,
        )
    except InvalidRegistrationResponse as exc:
        raise _bad_request(f"Passkey registration failed: {exc}") from exc

    if db.scalar(select(Passkey.id).where(Passkey.credential_id == verified.credential_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "This passkey is already registered")

    if challenge.pending_user is not None:
        assert auth_token is not None and auth_token.member is not None
        pending = challenge.pending_user
        _ensure_username_free(db, pending["username"])
        user = User(
            username=pending["username"],
            display_name=pending["display_name"],
            webauthn_user_id=base64url_to_bytes(pending["webauthn_user_id"]),
        )
        db.add(user)
        auth_token.member.user = user
    else:
        user = db.get_one(User, challenge.user_id)

    transports = credential.get("response", {}).get("transports") or []
    user.passkeys.append(
        Passkey(
            name=passkey_name,
            credential_id=verified.credential_id,
            public_key=verified.credential_public_key,
            sign_count=verified.sign_count,
            transports=[str(t) for t in transports],
            device_type=verified.credential_device_type.value,
            backed_up=verified.credential_backed_up,
        )
    )
    if auth_token is not None:
        auth_token.used_at = utcnow()
    db.commit()
    return user


def _ensure_username_free(db: DBSession, username: str) -> None:
    if db.scalar(select(User.id).where(User.username == username)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Username is already taken")


# --- WebAuthn: authentication -------------------------------------------------


def start_authentication(db: DBSession) -> tuple[uuid.UUID, dict[str, Any]]:
    options = generate_authentication_options(
        rp_id=get_settings().webauthn_rp_id,
        user_verification=UserVerificationRequirement.REQUIRED,
    )
    challenge = _store_challenge(
        db,
        WebAuthnChallenge(challenge=options.challenge, purpose=ChallengePurpose.AUTHENTICATION),
    )
    return challenge.id, options_to_json_dict(options)


def finish_authentication(
    db: DBSession, challenge_id: uuid.UUID, credential: dict[str, Any]
) -> User:
    challenge = _consume_challenge(db, challenge_id, ChallengePurpose.AUTHENTICATION)
    invalid = HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication failed")

    try:
        credential_id = base64url_to_bytes(credential["rawId"])
    except (KeyError, TypeError, ValueError) as exc:
        raise invalid from exc
    passkey = db.scalar(select(Passkey).where(Passkey.credential_id == credential_id))
    if passkey is None:
        raise invalid

    user_handle = credential.get("response", {}).get("userHandle")
    if user_handle and base64url_to_bytes(user_handle) != passkey.user.webauthn_user_id:
        raise invalid

    settings = get_settings()
    try:
        verified = verify_authentication_response(
            credential=credential,
            expected_challenge=challenge.challenge,
            expected_rp_id=settings.webauthn_rp_id,
            expected_origin=settings.webauthn_origin,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
            require_user_verification=True,
        )
    except InvalidAuthenticationResponse as exc:
        raise invalid from exc

    passkey.sign_count = verified.new_sign_count
    passkey.backed_up = verified.credential_backed_up
    passkey.last_used_at = utcnow()
    db.commit()
    return passkey.user
