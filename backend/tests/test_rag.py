"""RAG pieces tested offline with fake embedder/LLM (no network, no cost).

The fake embedder maps words to fixed axes, so "meaning" is predictable:
books about space point along axis 0, habits along axis 1, history along axis 2.
"""
import pytest

from app import models
from app.ai.provider import AIError, OpenRouterEmbedder
from app.models import EMBEDDING_DIM
from app.services import assistant_service, embedding_service, insights_service, recommend_service
from tests.conftest import NOW, make_book, make_category, make_past_loan, make_user

AXES = {"space": 0, "mars": 0, "planet": 0, "astronaut": 0, "stranded": 0,
        "habit": 1, "habits": 1, "routine": 1, "focus": 1,
        "history": 2, "rome": 2, "empire": 2}


class FakeEmbedder:
    name = "fake-embed"

    def __init__(self, fail=False):
        self.fail, self.calls = fail, 0

    def embed(self, texts):
        self.calls += 1
        if self.fail:
            raise AIError("rate limited")
        out = []
        for t in texts:
            v = [0.0] * EMBEDDING_DIM
            for w in t.lower().replace(".", " ").replace(",", " ").split():
                if w in AXES:
                    v[AXES[w]] += 1.0
            v[3] = 0.05  # tiny shared component so no vector is all-zero
            out.append(v)
        return out


class FakeLLM:
    name = "fake-claude"

    def __init__(self, fail=False):
        self.fail, self.seen = fail, None

    def generate(self, question, books):
        if self.fail:
            raise AIError("503")
        self.seen = [b.title for b in books]
        return "Try " + ", ".join(self.seen[:2])

    def brief(self, facts):
        self.seen = facts
        return "Brief: remind about overdue book."


@pytest.fixture
def shelf(db):
    sci, life, hist = make_category(db, "Science"), make_category(db, "Self-Help"), make_category(db, "History")
    books = {
        # descriptions deliberately avoid the word "survival": only meaning can connect them
        "martian": make_book(db, sci, "The Martian", tags=["mars"], author="Weir"),
        "hail": make_book(db, sci, "Project Hail Mary", tags=["space", "astronaut"], author="Weir"),
        "atomic": make_book(db, life, "Atomic Habits", tags=["habits", "routine"], author="Clear"),
        "spqr": make_book(db, hist, "SPQR", tags=["rome", "empire"], author="Beard"),
    }
    embedding_service.embed_stale(db, FakeEmbedder())
    return books


def test_embed_stale_only_reembeds_changed_books(db, shelf):
    emb = FakeEmbedder()
    assert embedding_service.embed_stale(db, emb) == {"total": 4, "embedded": 0, "up_to_date": 4}
    assert emb.calls == 0  # nothing changed -> no API call
    shelf["spqr"].description = "Rome from its founding"
    db.commit()
    assert embedding_service.embed_stale(db, emb)["embedded"] == 1


def test_semantic_search_finds_meaning_not_words(db, shelf):
    # "stranded astronaut" shares no title/description words with The Martian, only meaning (axis 0)
    qvec = FakeEmbedder().embed(["stranded astronaut on a planet"])[0]
    titles = [b.title for b in assistant_service.semantic_search(db, qvec)]
    assert set(titles[:2]) == {"The Martian", "Project Hail Mary"}
    assert "Atomic Habits" not in titles  # too far away (beyond MAX_DISTANCE)


def test_rrf_merge_rewards_books_found_by_both(db, shelf):
    m, h, a = shelf["martian"], shelf["hail"], shelf["atomic"]
    books, found_by = assistant_service.rrf_merge({"semantic": [h, m], "keyword": [m, a]})
    assert books[0].title == "The Martian"          # in both lists -> highest fused score
    assert found_by[m.id] == ["semantic", "keyword"]
    assert found_by[a.id] == ["keyword"]


def test_ask_hybrid_passes_only_retrieved_books_to_llm(db, shelf):
    stu, llm = make_user(db), FakeLLM()
    r = assistant_service.ask(db, stu, "a story about a stranded astronaut", provider=llm, embedder=FakeEmbedder())
    assert r["retrieval"] == "hybrid" and r["provider"] == "fake-claude" and r["error"] is None
    assert set(llm.seen) <= {"The Martian", "Project Hail Mary"}   # grounding: only real, relevant books
    assert "semantic" in r["found_by"][shelf["martian"].id]
    log = db.query(models.Activity).filter_by(action="assistant.ask").one()
    assert log.details["retrieval"] == "hybrid" and log.details["model"] == "fake-claude"


def test_ask_falls_back_when_embedding_api_fails(db, shelf):
    r = assistant_service.ask(db, make_user(db), "habits", provider=FakeLLM(), embedder=FakeEmbedder(fail=True))
    assert r["retrieval"] == "keyword" and "Semantic search unavailable" in r["error"]
    assert [b.title for b in r["books"]] == ["Atomic Habits"]


def test_ask_falls_back_when_llm_fails(db, shelf):
    r = assistant_service.ask(db, make_user(db), "habits", provider=FakeLLM(fail=True), embedder=FakeEmbedder())
    assert r["provider"] == "none" and "AI answer unavailable" in r["error"]
    assert "Atomic Habits" in r["answer"]   # templated answer still useful


def test_ask_skips_llm_when_nothing_retrieved(db, shelf):
    llm = FakeLLM()
    r = assistant_service.ask(db, make_user(db), "quantum chromodynamics", provider=llm, embedder=FakeEmbedder())
    assert r["books"] == [] and r["provider"] == "none" and llm.seen is None   # LLM never called


def test_recommended_books_come_first(db, shelf):
    class PicksSecond(FakeLLM):
        def generate(self, question, books):
            return f"Read {books[-1].title}."
    r = assistant_service.ask(db, make_user(db), "stranded astronaut space", provider=PicksSecond(), embedder=FakeEmbedder())
    assert r["books"][0].id in r["recommended"] and len(r["recommended"]) == 1


def test_close_in_meaning_recommendations(db, shelf):
    stu = make_user(db)
    make_past_loan(db, stu, shelf["martian"])
    recs = recommend_service.for_student(db, stu.id)
    close = recs["close_in_meaning"]
    assert close[0]["book"].title == "Project Hail Mary"
    assert close[0]["reason"] == "Close in meaning to “The Martian”"
    assert all(r["book"].title != "SPQR" for r in close)   # unrelated meaning is not suggested


def test_brief_facts_never_include_name_or_email(db, shelf):
    stu = make_user(db, email="secret.person@test.dev", name="Secret Person")
    make_past_loan(db, stu, shelf["martian"], days_late=3)
    llm = FakeLLM()
    brief, model = insights_service.ai_brief(db, stu.id, llm)
    assert brief.startswith("Brief") and model == "fake-claude"
    assert "Secret" not in llm.seen and "secret.person" not in llm.seen
    assert "Trust score" in llm.seen and "The Martian" in llm.seen


def test_openrouter_embedder_rejects_wrong_dimensions():
    class Client:
        def post(self, path, payload):
            return {"data": [{"index": 0, "embedding": [0.1, 0.2]}]}
    with pytest.raises(AIError):
        OpenRouterEmbedder(Client(), "m", EMBEDDING_DIM).embed(["x"])


def test_ai_brief_endpoint_returns_503_without_ai(client, db):
    make_user(db, "lib@test.dev", role="librarian", name="Lib")
    stu = make_user(db)
    t = client.post("/api/auth/login", json={"email": "lib@test.dev", "password": "secret123"}).json()["access_token"]
    r = client.post(f"/api/users/{stu.id}/ai-brief", headers={"Authorization": f"Bearer {t}"})
    assert r.status_code == 503 and "unavailable" in r.json()["detail"]
    assert NOW  # fixture import sanity
