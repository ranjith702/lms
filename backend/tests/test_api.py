"""End-to-end API tests through HTTP (FastAPI TestClient)."""
from tests.conftest import make_book, make_category, make_user


def login(client, email, password="secret123"):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_register_login_me_logout_and_history(client):
    r = client.post("/api/auth/register", json={"name": "Asha", "email": "Asha@Test.dev", "password": "longpass1"})
    assert r.status_code == 201 and r.json()["role"] == "student"
    assert client.post("/api/auth/register", json={"name": "A", "email": "asha@test.dev", "password": "longpass1"}).status_code in (409, 422)

    first = login(client, "asha@test.dev", "longpass1")
    assert first["previous_session"] is None
    token = first["access_token"]
    assert client.get("/api/auth/me", headers=auth(token)).json()["email"] == "asha@test.dev"
    assert client.post("/api/auth/logout", headers=auth(token)).status_code == 204
    # logged-out token is dead
    assert client.get("/api/auth/me", headers=auth(token)).status_code == 401

    second = login(client, "asha@test.dev", "longpass1")
    prev = second["previous_session"]
    assert prev and prev["logout_at"] is not None  # "last login / last logout" survives
    sessions = client.get("/api/auth/me/sessions", headers=auth(second["access_token"])).json()
    assert len(sessions) == 2


def test_wrong_password_and_missing_token(client, db):
    make_user(db)
    assert client.post("/api/auth/login", json={"email": "stu@test.dev", "password": "nope"}).status_code == 401
    assert client.get("/api/books").status_code == 401
    assert client.get("/api/books", headers=auth("garbage")).status_code == 401


def test_student_cannot_use_librarian_routes(client, db):
    make_user(db)
    t = login(client, "stu@test.dev")["access_token"]
    for method, path in [("get", "/api/dashboard"), ("get", "/api/loans"), ("get", "/api/fines"),
                         ("get", "/api/users/students"), ("get", "/api/activity"),
                         ("post", "/api/loans/1/approve"), ("delete", "/api/books/1")]:
        assert getattr(client, method)(path, headers=auth(t)).status_code == 403, path


def test_full_borrow_return_fine_flow(client, db):
    make_user(db, "lib@test.dev", role="librarian", name="Lib")
    make_user(db)
    lib = login(client, "lib@test.dev")["access_token"]
    stu = login(client, "stu@test.dev")["access_token"]

    cat = client.post("/api/categories", json={"name": "Science"}, headers=auth(lib)).json()
    book = client.post("/api/books", headers=auth(lib), json={
        "title": "Cosmos", "author": "Sagan", "category_id": cat["id"], "description": "The universe",
        "tags": ["Space", " astronomy "], "total_copies": 2}).json()
    assert book["tags"] == ["space", "astronomy"] and book["available_copies"] == 2

    assert [b["title"] for b in client.get("/api/books?q=universe", headers=auth(stu)).json()] == ["Cosmos"]

    r = client.post("/api/loans", json={"book_id": book["id"]}, headers=auth(stu))
    assert r.status_code == 201 and r.json()["loan"]["status"] == "borrowed"
    assert "Due back" in r.json()["message"]
    loan_id = r.json()["loan"]["id"]

    assert client.get("/api/books/%d" % book["id"], headers=auth(stu)).json()["available_copies"] == 1
    assert client.post("/api/loans", json={"book_id": book["id"]}, headers=auth(stu)).status_code == 409

    r = client.post(f"/api/loans/{loan_id}/return", headers=auth(stu))
    assert r.json()["status"] == "returned"
    assert client.get("/api/fines/me", headers=auth(stu)).json() == []  # on time -> no fine

    history = [a["action"] for a in client.get("/api/activity/me", headers=auth(stu)).json()]
    assert "loan.borrowed" in history and "loan.returned" in history and "auth.login" in history


def test_pending_approval_and_fine_payment_via_api(client, db):
    from datetime import datetime, timedelta, timezone

    from app import models
    make_user(db, "lib@test.dev", role="librarian", name="Lib")
    stu = make_user(db)
    cat = make_category(db)
    old = make_book(db, cat, "Old")
    now = datetime.now(timezone.utc)
    for days_late in (3, 3):
        loan = models.Loan(user_id=stu.id, book_id=old.id, status="returned", requested_at=now - timedelta(days=30),
                           borrowed_at=now - timedelta(days=30), due_at=now - timedelta(days=16),
                           returned_at=now - timedelta(days=16 - days_late))
        db.add(loan)
        db.flush()
        db.add(models.Fine(loan_id=loan.id, user_id=stu.id, days_late=days_late, amount=15))
    db.commit()
    wanted = make_book(db, cat, "Wanted")

    lib_t = login(client, "lib@test.dev")["access_token"]
    stu_t = login(client, "stu@test.dev")["access_token"]
    assert client.get("/api/auth/me/trust", headers=auth(stu_t)).json()["level"] == "approval"

    r = client.post("/api/loans", json={"book_id": wanted.id}, headers=auth(stu_t))
    assert r.json()["loan"]["status"] == "pending" and "approval" in r.json()["message"]
    pending = client.get("/api/loans?status=pending", headers=auth(lib_t)).json()
    assert len(pending) == 1 and pending[0]["student_name"] == "Stu"
    approved = client.post(f"/api/loans/{pending[0]['id']}/approve", headers=auth(lib_t)).json()
    assert approved["status"] == "borrowed" and approved["due_at"]

    fines = client.get("/api/fines?status=unpaid", headers=auth(lib_t)).json()
    assert len(fines) == 2 and fines[0]["book_title"] == "Old"
    for f in fines:
        assert client.post(f"/api/fines/{f['id']}/pay", headers=auth(lib_t)).json()["status"] == "paid"
    assert client.post(f"/api/fines/{fines[0]['id']}/waive", headers=auth(lib_t)).status_code == 409

    insights = client.get(f"/api/users/{stu.id}/insights", headers=auth(lib_t)).json()
    assert insights["trust"]["unpaid_fines"] == 0 and insights["suggestions"]
    dash = client.get("/api/dashboard", headers=auth(lib_t)).json()
    assert dash["copies_out"] == 1 and dash["pending"] == 0


def test_recommendations_and_assistant_endpoints(client, db):
    stu = make_user(db)
    cat = make_category(db, "Sci-Fi")
    make_book(db, cat, "Dune", tags=["space"])
    t = login(client, "stu@test.dev")["access_token"]
    recs = client.get("/api/recommendations/me", headers=auth(t)).json()
    assert set(recs) == {"close_in_meaning", "same_topic", "similar", "also_borrowed", "different", "popular"}
    ans = client.post("/api/assistant/ask", json={"question": "space adventure"}, headers=auth(t)).json()
    assert ans["provider"] == "none" and ans["retrieval"] == "keyword" and ans["books"][0]["title"] == "Dune"
    assert stu.id


def test_book_validation_and_delete_rules(client, db):
    make_user(db, "lib@test.dev", role="librarian", name="Lib")
    lib = login(client, "lib@test.dev")["access_token"]
    assert client.post("/api/books", headers=auth(lib), json={"title": "X", "author": "Y", "category_id": 999}).status_code == 400
    assert client.post("/api/books", headers=auth(lib), json={"title": "", "author": "Y", "category_id": 1}).status_code == 422
    cat = client.post("/api/categories", json={"name": "Misc"}, headers=auth(lib)).json()
    b = client.post("/api/books", headers=auth(lib), json={"title": "Temp", "author": "Y", "category_id": cat["id"]}).json()
    assert client.delete(f"/api/books/{b['id']}", headers=auth(lib)).status_code == 204
    assert client.get(f"/api/books/{b['id']}", headers=auth(lib)).status_code == 404


def test_category_full_crud(client, db):
    make_user(db, "lib@test.dev", role="librarian", name="Lib")
    make_user(db, "stu@test.dev")
    lib = login(client, "lib@test.dev")["access_token"]
    stu = login(client, "stu@test.dev")["access_token"]
    # Create
    c = client.post("/api/categories", json={"name": "Poetry"}, headers=auth(lib))
    assert c.status_code == 201
    cid = c.json()["id"]
    assert client.post("/api/categories", json={"name": "poetry"}, headers=auth(lib)).status_code == 409
    # Update (rename + description), case-insensitive clash with another category is rejected
    client.post("/api/categories", json={"name": "Drama"}, headers=auth(lib))
    r = client.put(f"/api/categories/{cid}", json={"name": "Verse", "description": "Poems"}, headers=auth(lib))
    assert r.status_code == 200 and r.json()["name"] == "Verse" and r.json()["description"] == "Poems"
    assert client.put(f"/api/categories/{cid}", json={"name": "DRAMA"}, headers=auth(lib)).status_code == 409
    assert client.put(f"/api/categories/{cid}", json={"name": "Verse"}, headers=auth(lib)).status_code == 200  # same name ok
    assert client.put("/api/categories/999", json={"name": "Ghost"}, headers=auth(lib)).status_code == 404
    # Students may read but not change
    assert client.put(f"/api/categories/{cid}", json={"name": "X1"}, headers=auth(stu)).status_code == 403
    assert client.delete(f"/api/categories/{cid}", headers=auth(stu)).status_code == 403
    # Delete is blocked while books reference it, allowed once empty
    b = client.post("/api/books", headers=auth(lib), json={"title": "Odes", "author": "Keats", "category_id": cid}).json()
    assert client.delete(f"/api/categories/{cid}", headers=auth(lib)).status_code == 409
    assert client.delete(f"/api/books/{b['id']}", headers=auth(lib)).status_code == 204
    assert client.delete(f"/api/categories/{cid}", headers=auth(lib)).status_code == 204
    assert client.delete(f"/api/categories/{cid}", headers=auth(lib)).status_code == 404
    names = [x["name"] for x in client.get("/api/categories", headers=auth(stu)).json()]
    assert names == ["Drama"]


def test_public_shelf_needs_no_login_and_hides_stock_details(client, db):
    cat = make_category(db, "Sci-Fi")
    for i in range(3):
        make_book(db, cat, title=f"Book {i}", copies=2)
    r = client.get("/api/public/shelf")
    assert r.status_code == 200
    body = r.json()
    assert [c["name"] for c in body["categories"]] == ["Sci-Fi"] and body["categories"][0]["book_count"] == 3
    assert len(body["books"]) == 3
    assert set(body["books"][0]) == {"id", "title", "author", "category_name", "cover_color"}


def test_public_shelf_spreads_books_across_categories(client, db):
    big, small = make_category(db, "Big"), make_category(db, "Small")
    for i in range(45):
        make_book(db, big, title=f"Big {i}")
    make_book(db, small, title="Only small one")
    books = client.get("/api/public/shelf").json()["books"]
    assert len(books) == 40
    assert "Only small one" in [b["title"] for b in books]
