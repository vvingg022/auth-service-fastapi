def test_register_success(client):
    r = client.post(
        "/api/auth/register",
        json={"name": "Vaibhavi", "email": "v@test.com", "password": "Test12345"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["email"] == "v@test.com"
    assert body["role"] == "user"
    assert "password" not in body
    assert "password_hash" not in body


def test_register_duplicate_email(client):
    data = {"name": "A", "email": "v@test.com", "password": "Test12345"}
    assert client.post("/api/auth/register", json=data).status_code == 201
    assert client.post("/api/auth/register", json=data).status_code == 409


def test_register_validation_error(client):
    r = client.post(
        "/api/auth/register",
        json={"name": "A", "email": "bad", "password": "123"},
    )
    assert r.status_code == 422


def test_register_cannot_choose_admin_role(client):
    r = client.post(
        "/api/auth/register",
        json={"name": "Hack", "email": "h@test.com", "password": "Test12345", "role": "admin"},
    )
    assert r.status_code == 201
    assert r.json()["role"] == "user"


def test_login_success_sets_tokens(client, make_user, login):
    make_user()
    r = login()
    assert r.status_code == 200
    assert "access_token" in r.json()
    assert client.cookies.get("refreshToken")


def test_login_wrong_password(make_user, login):
    make_user()
    r = login(password="wrongpass1")
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_login_unknown_email_same_message(login):
    r = login(email="nobody@test.com")
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid email or password"


def test_me_with_token(client, make_user, auth_header):
    make_user()
    r = client.get("/api/auth/me", headers=auth_header())
    assert r.status_code == 200
    assert r.json()["email"] == "user@test.com"


def test_me_without_token(client):
    # Older FastAPI returns 403, newer returns 401. Both mean "not authenticated".
    assert client.get("/api/auth/me").status_code in (401, 403)


def test_me_with_fake_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer abc123"})
    assert r.status_code == 401


def test_refresh_issues_new_access_token(client, make_user, login):
    make_user()
    login()
    r = client.post("/api/auth/refresh")
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_old_refresh_token_stops_working_after_rotation(client, make_user, login):
    make_user()
    login()
    old_token = client.cookies.get("refreshToken")

    assert client.post("/api/auth/refresh").status_code == 200  # rotates the token

    client.cookies.clear()
    r = client.post("/api/auth/refresh", headers={"Cookie": f"refreshToken={old_token}"})
    assert r.status_code == 401


def test_logout_revokes_refresh(client, make_user, login, auth_header):
    make_user()
    headers = auth_header()
    assert client.post("/api/auth/logout", headers=headers).status_code == 200
    assert client.post("/api/auth/refresh").status_code == 401


def test_refresh_without_cookie(client):
    assert client.post("/api/auth/refresh").status_code == 401