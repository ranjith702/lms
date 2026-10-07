"""Live API smoke test against a RUNNING server + seeded DB.

Usage (from backend/, server running):  python -m scripts.smoke_api [--base http://127.0.0.1:8000]
Read-mostly: it borrows and returns ONE book as Kiran (new student) so the flow is exercised, leaving
the stock count unchanged. Prints a PASS/FAIL table and exits 1 on any failure.
"""
import sys

import httpx

BASE = sys.argv[sys.argv.index("--base") + 1] if "--base" in sys.argv else "http://127.0.0.1:8000"
results: list[tuple[str, str, int, bool, str]] = []


def check(who, method, path, token=None, expect=200, **kw):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    r = httpx.request(method, BASE + "/api" + path, headers=headers, timeout=10, **kw)
    ok = r.status_code == expect
    note = "" if ok else r.text[:80]
    results.append((who, f"{method} {path}", r.status_code, ok, note))
    try:
        return r.json()
    except ValueError:
        return None


def login(email, pw):
    return check(email.split("@")[0], "POST", "/auth/login", json={"email": email, "password": pw})["access_token"]


def main():
    check("anon", "GET", "/health")
    check("anon", "GET", "/books", expect=401)

    lib = login("librarian@library.dev", "Librarian@123")
    kiran = login("kiran@library.dev", "Student@123")
    meera = login("meera@library.dev", "Student@123")

    # student side
    books = check("kiran", "GET", "/books", kiran)
    check("kiran", "GET", "/books?q=space", kiran)
    check("kiran", "GET", f"/books/{books[0]['id']}", kiran)
    check("kiran", "GET", "/categories", kiran)
    check("kiran", "GET", "/auth/me", kiran)
    check("kiran", "GET", "/auth/me/sessions", kiran)
    trust = check("kiran", "GET", "/auth/me/trust", kiran)
    check("kiran", "GET", "/recommendations/me", kiran)
    check("kiran", "POST", "/assistant/ask", kiran, json={"question": "books about habits"})
    check("kiran", "GET", "/fines/me", kiran)
    check("kiran", "GET", "/activity/me", kiran)
    check("kiran", "GET", "/dashboard", kiran, expect=403)

    available = next(b for b in books if b["available_copies"] > 0)
    if trust and trust["level"] == "instant":
        loan = check("kiran", "POST", "/loans", kiran, expect=201, json={"book_id": available["id"]})
        check("kiran", "GET", "/loans/me", kiran)
        if loan:
            check("kiran", "POST", f"/loans/{loan['loan']['id']}/return", kiran)

    check("meera", "GET", "/auth/me/trust", meera)
    check("meera", "POST", "/loans", meera, expect=403, json={"book_id": available["id"]})  # blocked

    # librarian side
    check("lib", "GET", "/dashboard", lib)
    students = check("lib", "GET", "/users/students", lib)
    check("lib", "GET", f"/users/{students[0]['id']}/insights", lib)
    check("lib", "GET", "/loans", lib)
    check("lib", "GET", "/loans?status=overdue", lib)
    check("lib", "GET", "/loans?status=pending", lib)
    check("lib", "GET", "/fines?status=unpaid", lib)
    check("lib", "GET", "/activity?limit=20", lib)
    check("lib", "POST", "/books", lib, expect=422, json={"title": ""})  # validation works

    for t in (kiran, meera, lib):
        check("all", "POST", "/auth/logout", t, expect=204)
    check("kiran", "GET", "/auth/me", kiran, expect=401)  # logged-out token rejected

    width = max(len(r[1]) for r in results)
    for who, call, code, ok, note in results:
        print(f"{'PASS' if ok else 'FAIL'}  {who:<6} {call:<{width}}  {code}  {note}")
    failed = sum(not r[3] for r in results)
    print(f"\n{len(results) - failed}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
