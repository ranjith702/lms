"""httpOnly auth cookie + login rate limiting (mentor review, 2026-10-27)."""
from app.routers.auth import login_limiter
from tests.conftest import make_user

GOOD = {"email": "stu@test.dev", "password": "secret123"}
BAD = {"email": "stu@test.dev", "password": "wrong-one"}


def test_login_sets_httponly_cookie_that_authenticates_without_a_header(client, db):
    make_user(db)
    r = client.post("/api/auth/login", json=GOOD)
    assert r.status_code == 200
    cookie = r.headers["set-cookie"].lower()
    assert "lms_session=" in cookie and "httponly" in cookie and "samesite=lax" in cookie and "path=/api" in cookie

    # No Authorization header: the cookie alone identifies the browser.
    assert client.get("/api/auth/me").json()["email"] == "stu@test.dev"

    # Logout ends the session server-side and clears the cookie.
    assert client.post("/api/auth/logout").status_code == 204
    assert "lms_session" not in client.cookies
    assert client.get("/api/auth/me").status_code == 401


def test_stolen_cookie_value_is_dead_after_logout(client, db):
    make_user(db)
    token = client.post("/api/auth/login", json=GOOD).json()["access_token"]
    client.post("/api/auth/logout")
    client.cookies.set("lms_session", token, path="/api")  # replay the old value by hand
    assert client.get("/api/auth/me").status_code == 401


def test_repeated_wrong_passwords_lock_the_account_for_that_ip(client, db):
    make_user(db)
    for _ in range(5):
        assert client.post("/api/auth/login", json=BAD).status_code == 401
    r = client.post("/api/auth/login", json=GOOD)  # even the right password waits
    assert r.status_code == 429
    assert int(r.headers["retry-after"]) > 0

    # Another account from the same IP is still allowed (per-IP limit is higher).
    make_user(db, email="other@test.dev")
    assert client.post("/api/auth/login", json={"email": "other@test.dev", "password": "secret123"}).status_code == 200


def test_lock_lifts_when_the_window_passes(client, db, monkeypatch):
    make_user(db)
    now = [1000.0]
    monkeypatch.setattr(login_limiter, "clock", lambda: now[0])
    for _ in range(5):
        client.post("/api/auth/login", json=BAD)
    assert client.post("/api/auth/login", json=GOOD).status_code == 429
    now[0] += login_limiter.window + 1
    assert client.post("/api/auth/login", json=GOOD).status_code == 200


def test_successful_login_resets_the_account_counter(client, db):
    make_user(db)
    for _ in range(4):
        client.post("/api/auth/login", json=BAD)
    assert client.post("/api/auth/login", json=GOOD).status_code == 200
    for _ in range(4):  # would be 8 in a row without the reset
        assert client.post("/api/auth/login", json=BAD).status_code == 401
    assert client.post("/api/auth/login", json=GOOD).status_code == 200


def test_per_ip_limit_stops_credential_stuffing_across_emails(client, db):
    for i in range(20):
        assert client.post("/api/auth/login", json={"email": f"u{i}@test.dev", "password": "x"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "u99@test.dev", "password": "x"}).status_code == 429
