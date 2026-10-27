"""Books + categories."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app import schemas
from app.core.security import get_current_user, require_librarian
from app.db import get_db
from app.models import Book, Category, Loan, User
from app.routers._convert import book_out
from app.ai.provider import get_embedder
from app.services import activity
from app.services.embedding_service import embed_after_change

router = APIRouter(tags=["catalog"])
SHELF_LIMIT = 40


@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(
        select(Category, func.count(Book.id)).outerjoin(Book, Book.category_id == Category.id)
        .group_by(Category.id).order_by(Category.name)
    ).all()
    return [schemas.CategoryOut(id=c.id, name=c.name, description=c.description, book_count=n) for c, n in rows]


@router.get("/public/shelf", response_model=schemas.ShelfOut)
def public_shelf(db: Session = Depends(get_db)):
    """No login needed: what the landing page shows. Titles, authors and categories only."""
    rows = db.execute(
        select(Category, func.count(Book.id)).outerjoin(Book, Book.category_id == Category.id)
        .group_by(Category.id).order_by(Category.name)
    ).all()
    # Deal books out one category at a time so every shelf is represented, not just the first few by id.
    by_cat: dict[int, list[Book]] = {}
    for b in db.scalars(select(Book).options(joinedload(Book.category)).order_by(Book.id)):
        by_cat.setdefault(b.category_id, []).append(b)
    queues, books = list(by_cat.values()), []
    while queues and len(books) < SHELF_LIMIT:
        queues = [q for q in queues if q]
        books += [q.pop(0) for q in queues][: SHELF_LIMIT - len(books)]
    return schemas.ShelfOut(
        categories=[schemas.CategoryOut(id=c.id, name=c.name, description=c.description, book_count=n) for c, n in rows],
        books=[schemas.ShelfBook(id=b.id, title=b.title, author=b.author, category_name=b.category.name,
                                 cover_color=b.cover_color) for b in books],
    )


@router.post("/categories", response_model=schemas.CategoryOut, status_code=201)
def create_category(body: schemas.CategoryIn, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    if db.scalar(select(Category).where(func.lower(Category.name) == body.name.lower())):
        raise HTTPException(409, "Category already exists")
    c = Category(name=body.name.strip(), description=body.description)
    db.add(c)
    db.flush()
    activity.log(db, lib.id, "category.created", "category", c.id, name=c.name)
    db.commit()
    return schemas.CategoryOut(id=c.id, name=c.name, description=c.description)


def _get_category(db: Session, category_id: int) -> Category:
    c = db.get(Category, category_id)
    if c is None:
        raise HTTPException(404, "Category not found")
    return c


def _book_count(db: Session, category_id: int) -> int:
    return db.scalar(select(func.count()).select_from(Book).where(Book.category_id == category_id))


@router.put("/categories/{category_id}", response_model=schemas.CategoryOut)
def update_category(category_id: int, body: schemas.CategoryIn, db: Session = Depends(get_db),
                    lib: User = Depends(require_librarian)):
    c = _get_category(db, category_id)
    name = body.name.strip()
    clash = db.scalar(select(Category).where(func.lower(Category.name) == name.lower(), Category.id != category_id))
    if clash:
        raise HTTPException(409, "Category already exists")
    renamed = c.name != name
    c.name, c.description = name, body.description
    activity.log(db, lib.id, "category.updated", "category", c.id, name=c.name)
    db.commit()
    if renamed:
        # The category name is part of every book's embedded text, so a rename makes those embeddings stale.
        book_ids = list(db.scalars(select(Book.id).where(Book.category_id == category_id)))
        if book_ids:
            embed_after_change(db, get_embedder(), book_ids)
    return schemas.CategoryOut(id=c.id, name=c.name, description=c.description, book_count=_book_count(db, c.id))


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: int, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    c = _get_category(db, category_id)
    n = _book_count(db, category_id)
    if n:
        raise HTTPException(409, f"Category still has {n} book(s); move or delete them first")
    activity.log(db, lib.id, "category.deleted", "category", c.id, name=c.name)
    db.delete(c)
    db.commit()


@router.get("/books", response_model=list[schemas.BookOut])
def list_books(
    q: str | None = Query(None, max_length=200),
    category_id: int | None = None,
    available: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    stmt = select(Book).options(joinedload(Book.category)).order_by(Book.title)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(
            Book.title.ilike(like), Book.author.ilike(like),
            Book.search.op("@@")(func.websearch_to_tsquery("english", q)),
        ))
    if category_id:
        stmt = stmt.where(Book.category_id == category_id)
    if available:
        stmt = stmt.where(Book.available_copies > 0)
    return [book_out(b) for b in db.scalars(stmt)]


def _get_book(db: Session, book_id: int) -> Book:
    book = db.scalar(select(Book).options(joinedload(Book.category)).where(Book.id == book_id))
    if book is None:
        raise HTTPException(404, "Book not found")
    return book


@router.get("/books/{book_id}", response_model=schemas.BookOut)
def get_book(book_id: int, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return book_out(_get_book(db, book_id))


def _check_category(db: Session, category_id: int) -> None:
    if db.get(Category, category_id) is None:
        raise HTTPException(400, "Unknown category")


@router.post("/books", response_model=schemas.BookOut, status_code=201)
def create_book(body: schemas.BookIn, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    _check_category(db, body.category_id)
    data = body.model_dump()
    data["tags"] = [t.strip().lower() for t in body.tags if t.strip()]
    book = Book(**data, available_copies=body.total_copies)
    db.add(book)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A book with this ISBN already exists")
    activity.log(db, lib.id, "book.created", "book", book.id, title=book.title)
    db.commit()
    embed_after_change(db, get_embedder(), book.id)   # best effort; never blocks saving the book
    return book_out(_get_book(db, book.id))


@router.put("/books/{book_id}", response_model=schemas.BookOut)
def update_book(book_id: int, body: schemas.BookIn, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    book = _get_book(db, book_id)
    _check_category(db, body.category_id)
    out_now = book.total_copies - book.available_copies
    if body.total_copies < out_now:
        raise HTTPException(409, f"{out_now} copies are out on loan; total cannot be lower than that")
    for field, value in body.model_dump().items():
        setattr(book, field, value)
    book.tags = [t.strip().lower() for t in body.tags if t.strip()]
    book.available_copies = body.total_copies - out_now
    activity.log(db, lib.id, "book.updated", "book", book.id, title=book.title)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "A book with this ISBN already exists")
    embed_after_change(db, get_embedder(), book_id)
    return book_out(_get_book(db, book_id))


@router.delete("/books/{book_id}", status_code=204)
def delete_book(book_id: int, db: Session = Depends(get_db), lib: User = Depends(require_librarian)):
    book = _get_book(db, book_id)
    if db.scalar(select(func.count()).select_from(Loan).where(Loan.book_id == book_id)):
        raise HTTPException(409, "Book has loan history; set copies instead of deleting to keep records intact")
    activity.log(db, lib.id, "book.deleted", "book", book.id, title=book.title)
    db.delete(book)
    db.commit()
