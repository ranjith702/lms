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


@router.get("/categories", response_model=list[schemas.CategoryOut])
def list_categories(db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    rows = db.execute(
        select(Category, func.count(Book.id)).outerjoin(Book, Book.category_id == Category.id)
        .group_by(Category.id).order_by(Category.name)
    ).all()
    return [schemas.CategoryOut(id=c.id, name=c.name, description=c.description, book_count=n) for c, n in rows]


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
