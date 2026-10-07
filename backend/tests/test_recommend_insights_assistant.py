from app.services import assistant_service, insights_service, recommend_service
from tests.conftest import NOW, make_book, make_category, make_past_loan, make_user


def _library(db):
    scifi, hist, poetry = make_category(db, "Sci-Fi"), make_category(db, "History"), make_category(db, "Poetry")
    books = {
        "dune": make_book(db, scifi, "Dune", tags=["space", "politics"], author="Herbert"),
        "found": make_book(db, scifi, "Foundation", tags=["space", "empire"], author="Asimov"),
        "robots": make_book(db, scifi, "I, Robot", tags=["robots"], author="Asimov"),
        "rome": make_book(db, hist, "SPQR", tags=["empire", "politics"], author="Beard"),
        "odes": make_book(db, poetry, "Odes", tags=["verse"], author="Keats"),
    }
    return books


def test_new_student_gets_popular_books(db):
    books = _library(db)
    other = make_user(db, "o@test.dev")
    make_past_loan(db, other, books["odes"])
    stu = make_user(db)
    recs = recommend_service.for_student(db, stu.id)
    assert recs["popular"][0]["book"].title == "Odes"


def test_recommendations_cover_same_topic_similar_also_borrowed_and_different(db):
    books = _library(db)
    stu = make_user(db)
    make_past_loan(db, stu, books["dune"])
    # another reader who read Dune also read Odes (no shared tags -> only co-borrow can find it)
    other = make_user(db, "o@test.dev")
    make_past_loan(db, other, books["dune"])
    make_past_loan(db, other, books["odes"])

    recs = recommend_service.for_student(db, stu.id)
    titles = lambda key: [r["book"].title for r in recs[key]]
    # each book appears in only ONE section (no duplicates on screen), best section wins
    shown = sum((titles(k) for k in recs), [])
    assert len(shown) == len(set(shown))
    assert "I, Robot" in titles("same_topic")              # same category, no shared tags
    assert "Dune" not in sum((titles(k) for k in recs), [])  # never recommend what you read
    assert titles("similar")[0] in ("Foundation", "SPQR")    # shares tags with Dune
    assert "Odes" in titles("also_borrowed")
    assert set(titles("different")) <= {"SPQR", "Odes"}      # categories never borrowed
    assert all(r["reason"] for k in recs for r in recs[k])


def test_reason_keeps_author_name_casing(db):
    """LMS-BUG-009: str.capitalize() lowercased 'Asimov' to 'asimov'."""
    books = _library(db)
    stu = make_user(db)
    make_past_loan(db, stu, books["found"])
    recs = recommend_service.for_student(db, stu.id)
    robot = next(r for r in recs["similar"] if r["book"].title == "I, Robot")
    assert robot["reason"].startswith("More by Asimov")


def test_librarian_insights_explain_the_student(db):
    books = _library(db)
    stu = make_user(db)
    make_past_loan(db, stu, books["dune"], days_late=4)
    make_past_loan(db, stu, books["found"])
    make_past_loan(db, stu, books["robots"], returned=False)  # overdue now
    data = insights_service.for_student(db, stu.id, now=NOW)
    assert data["trust"].score < 100
    assert data["favorite_categories"][0]["name"] == "Sci-Fi"
    assert data["overdue"][0]["title"] == "I, Robot"
    assert data["on_time_rate"] == 50
    assert any("overdue" in s.lower() for s in data["suggestions"])


def test_assistant_finds_books_by_meaning_words(db):
    _library(db)
    stu = make_user(db)
    answer = assistant_service.ask(db, stu, "something about space empire")
    titles = [b.title for b in answer["books"]]
    assert "Foundation" in titles
    assert answer["provider"] == "none"
    assert answer["answer"]


def test_assistant_handles_no_match(db):
    _library(db)
    answer = assistant_service.ask(db, make_user(db), "underwater basket weaving")
    assert answer["books"] == [] and "couldn't find" in answer["answer"].lower()
