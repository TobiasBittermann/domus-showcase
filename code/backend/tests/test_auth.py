from app.models import User
from app.services import auth
from tests.flows import invite_token, login, register
from tests.softauthn import SoftAuthenticator


def test_me_requires_login(client):
    assert client.get("/api/auth/me").status_code == 401


def test_token_info(client, db, household):
    token = invite_token(db, household)
    r = client.get(f"/api/auth/tokens/{token}")
    assert r.status_code == 200
    assert r.json()["purpose"] == "invite"
    assert r.json()["household_name"] == "Test household"
    assert client.get("/api/auth/tokens/unbekannt").status_code == 404


def test_register_via_invite_logs_in(client, db, household):
    register(client, invite_token(db, household))

    me = client.get("/api/auth/me").json()
    assert me["username"] == "tobi"
    assert me["role"] == "admin"
    assert me["household"]["name"] == "Test household"


def test_invite_is_single_use(client, db, household):
    token = invite_token(db, household)
    register(client, token)
    r = client.post(
        "/api/auth/register/options",
        json={"token": token, "username": "anna", "display_name": "Anna"},
    )
    assert r.status_code == 404


def test_username_must_be_unique(client, db, household):
    register(client, invite_token(db, household))
    r = client.post(
        "/api/auth/register/options",
        json={"token": invite_token(db, household), "username": "tobi", "display_name": "X"},
    )
    assert r.status_code == 409


def test_logout_and_login_with_passkey(client, db, household):
    authenticator = register(client, invite_token(db, household))

    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/auth/me").status_code == 401

    user = login(client, authenticator)
    assert user["username"] == "tobi"
    assert client.get("/api/auth/me").status_code == 200


def test_login_rejects_unknown_passkey(client, db, household):
    register(client, invite_token(db, household))
    client.post("/api/auth/logout")

    stranger = SoftAuthenticator(user_handle=b"x" * 64)
    body = client.post("/api/auth/login/options").json()
    r = client.post(
        "/api/auth/login/verify",
        json={"challenge_id": body["challenge_id"], "credential": stranger.get(body["options"])},
    )
    assert r.status_code == 401


def test_challenge_cannot_be_reused(client, db, household):
    authenticator = register(client, invite_token(db, household))
    body = client.post("/api/auth/login/options").json()
    payload = {
        "challenge_id": body["challenge_id"],
        "credential": authenticator.get(body["options"]),
    }
    assert client.post("/api/auth/login/verify", json=payload).status_code == 200
    assert client.post("/api/auth/login/verify", json=payload).status_code == 400


def test_wrong_origin_is_rejected(client, db, household):
    authenticator = SoftAuthenticator(origin="https://evil.example")
    body = client.post(
        "/api/auth/register/options",
        json={"token": invite_token(db, household), "username": "tobi", "display_name": "Tobi"},
    ).json()
    r = client.post(
        "/api/auth/register/verify",
        json={
            "challenge_id": body["challenge_id"],
            "credential": authenticator.create(body["options"]),
        },
    )
    assert r.status_code == 400


def test_add_and_delete_passkeys(client, db, household):
    register(client, invite_token(db, household))
    [first] = client.get("/api/auth/passkeys").json()

    # The last passkey must not be deletable
    assert client.delete(f"/api/auth/passkeys/{first['id']}").status_code == 409

    second = SoftAuthenticator()
    body = client.post("/api/auth/passkeys/options").json()
    r = client.post(
        "/api/auth/passkeys/verify",
        json={
            "challenge_id": body["challenge_id"],
            "credential": second.create(body["options"]),
            "passkey_name": "Laptop",
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["name"] == "Laptop"

    assert client.delete(f"/api/auth/passkeys/{first['id']}").status_code == 204
    client.post("/api/auth/logout")
    assert login(client, second)["username"] == "tobi"


def test_recovery_link_adds_new_passkey(client, db, household):
    register(client, invite_token(db, household))
    client.post("/api/auth/logout")

    tobi = db.query(User).filter_by(username="tobi").one()
    token, _ = auth.create_recovery(db, tobi)
    assert client.get(f"/api/auth/tokens/{token}").json()["username"] == "tobi"

    new_device = SoftAuthenticator()
    body = client.post("/api/auth/register/options", json={"token": token}).json()
    assert body["options"]["user"]["name"] == "tobi"
    r = client.post(
        "/api/auth/register/verify",
        json={
            "challenge_id": body["challenge_id"],
            "credential": new_device.create(body["options"]),
        },
    )
    assert r.status_code == 200, r.text
    assert len(client.get("/api/auth/passkeys").json()) == 2

    client.post("/api/auth/logout")
    assert login(client, new_device)["username"] == "tobi"
