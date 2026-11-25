def test_security_headers_present(client):
    r = client.get("/health")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"


def test_api_responses_are_not_cached(client, make_user, login):
    make_user()
    r = login()
    assert r.headers["cache-control"] == "no-store"


def test_cors_allows_listed_origin(client):
    r = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_cors_blocks_unknown_origin(client):
    r = client.options(
        "/api/auth/login",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert r.status_code == 400
    assert "access-control-allow-origin" not in r.headers


def test_rate_limit_returns_429(client, rate_limit_on):
    codes = []
    for i in range(6):
        r = client.post(
            "/api/auth/register",
            json={"name": "T", "email": f"u{i}@test.com", "password": "Test12345"},
        )
        codes.append(r.status_code)

    assert codes[:5] == [201] * 5
    assert codes[5] == 429