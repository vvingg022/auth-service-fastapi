def wrong_attempts(login, count):
    return [login(password="wrongpass1").status_code for _ in range(count)]


def test_account_locks_after_five_failures(make_user, login):
    make_user()
    assert wrong_attempts(login, 4) == [401, 401, 401, 401]
    assert login(password="wrongpass1").status_code == 423  # the 5th


def test_correct_password_refused_while_locked(make_user, login):
    make_user()
    wrong_attempts(login, 5)
    assert login().status_code == 423


def test_success_resets_failure_counter(make_user, login):
    make_user()
    assert wrong_attempts(login, 3) == [401, 401, 401]
    assert login().status_code == 200
    assert wrong_attempts(login, 4) == [401, 401, 401, 401]  # still not locked


def test_admin_can_unlock(client, make_user, login, auth_header):
    user_id = make_user(email="user@test.com")
    make_user(email="admin@test.com", role="admin")

    wrong_attempts(login, 5)
    assert login().status_code == 423

    admin_headers = auth_header("admin@test.com")
    r = client.post(f"/api/admin/users/{user_id}/unlock", headers=admin_headers)
    assert r.status_code == 200

    assert login().status_code == 200