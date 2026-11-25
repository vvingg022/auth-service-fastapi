def test_normal_user_blocked_from_admin(client, make_user, auth_header):
    make_user()
    r = client.get("/api/admin/users", headers=auth_header())
    assert r.status_code == 403


def test_admin_can_list_users(client, make_user, auth_header):
    make_user(email="admin@test.com", role="admin")
    make_user(email="user@test.com")
    r = client.get("/api/admin/users", headers=auth_header("admin@test.com"))
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_admin_can_change_role(client, make_user, auth_header):
    make_user(email="admin@test.com", role="admin")
    user_id = make_user(email="user@test.com")
    r = client.patch(
        f"/api/admin/users/{user_id}/role",
        json={"role": "admin"},
        headers=auth_header("admin@test.com"),
    )
    assert r.status_code == 200
    assert r.json()["role"] == "admin"


def test_admin_cannot_change_own_role(client, make_user, auth_header):
    admin_id = make_user(email="admin@test.com", role="admin")
    r = client.patch(
        f"/api/admin/users/{admin_id}/role",
        json={"role": "user"},
        headers=auth_header("admin@test.com"),
    )
    assert r.status_code == 400


def test_invalid_role_rejected(client, make_user, auth_header):
    make_user(email="admin@test.com", role="admin")
    user_id = make_user(email="user@test.com")
    r = client.patch(
        f"/api/admin/users/{user_id}/role",
        json={"role": "superuser"},
        headers=auth_header("admin@test.com"),
    )
    assert r.status_code == 422


def test_change_role_unknown_user(client, make_user, auth_header):
    make_user(email="admin@test.com", role="admin")
    r = client.patch(
        "/api/admin/users/999/role",
        json={"role": "user"},
        headers=auth_header("admin@test.com"),
    )
    assert r.status_code == 404


def test_admin_endpoint_without_token(client):
    assert client.get("/api/admin/users").status_code in (401, 403)