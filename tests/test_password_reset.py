import pytest


@pytest.fixture
def captured_tokens(monkeypatch):
    """Replaces the email sender, so the test can read the token that would be emailed."""
    tokens = []
    monkeypatch.setattr(
        "app.routers.password.send_reset_email",
        lambda email, token: tokens.append(token),
    )
    return tokens


def request_reset(client, email="user@test.com"):
    return client.post("/api/auth/forgot-password", json={"email": email})


def test_forgot_password_known_email(client, make_user, captured_tokens):
    make_user()
    r = request_reset(client)
    assert r.status_code == 200
    assert len(captured_tokens) == 1


def test_forgot_password_unknown_email_gives_same_answer(client, make_user, captured_tokens):
    make_user()
    known = request_reset(client, "user@test.com")
    unknown = request_reset(client, "nobody@test.com")
    assert known.status_code == unknown.status_code == 200
    assert known.json() == unknown.json()
    assert len(captured_tokens) == 1  # only the real user got an email


def test_full_reset_flow(client, make_user, login, captured_tokens):
    make_user()
    request_reset(client)

    r = client.post(
        "/api/auth/reset-password",
        json={"token": captured_tokens[0], "new_password": "NewPass12345"},
    )
    assert r.status_code == 200

    assert login(password="Test12345").status_code == 401   # old password dead
    assert login(password="NewPass12345").status_code == 200  # new password works


def test_reset_token_is_single_use(client, make_user, captured_tokens):
    make_user()
    request_reset(client)
    body = {"token": captured_tokens[0], "new_password": "NewPass12345"}

    assert client.post("/api/auth/reset-password", json=body).status_code == 200
    assert client.post("/api/auth/reset-password", json=body).status_code == 400


def test_fake_token_rejected(client):
    r = client.post(
        "/api/auth/reset-password",
        json={"token": "thisisnotarealtoken123", "new_password": "NewPass12345"},
    )
    assert r.status_code == 400


def test_weak_password_rejected_and_token_survives(client, make_user, captured_tokens):
    make_user()
    request_reset(client)
    token = captured_tokens[0]

    weak = client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "123"}
    )
    assert weak.status_code == 422

    good = client.post(
        "/api/auth/reset-password", json={"token": token, "new_password": "NewPass12345"}
    )
    assert good.status_code == 200


def test_reset_revokes_existing_sessions(client, make_user, login, captured_tokens):
    make_user()
    login()  # creates a session (refresh cookie)
    request_reset(client)
    client.post(
        "/api/auth/reset-password",
        json={"token": captured_tokens[0], "new_password": "NewPass12345"},
    )
    assert client.post("/api/auth/refresh").status_code == 401


def test_reset_clears_lockout(client, make_user, login, captured_tokens):
    make_user()
    for _ in range(5):
        login(password="wrongpass1")
    assert login().status_code == 423

    request_reset(client)
    client.post(
        "/api/auth/reset-password",
        json={"token": captured_tokens[0], "new_password": "NewPass12345"},
    )
    assert login(password="NewPass12345").status_code == 200