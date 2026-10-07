"""Seed demo data.  Usage (from backend/):  python -m scripts.seed  [--reset]

Without --reset it refuses to touch a database that already has users (protects your data).
Demo logins (password for all students: Student@123, librarian: Librarian@123):
  librarian@library.dev  - Librarian
  asha@library.dev       - reliable reader, all returns on time  -> instant borrow
  ravi@library.dev       - two late returns + unpaid fines         -> needs approval
  meera@library.dev      - overdue book + late returns + fine      -> blocked
  kiran@library.dev      - brand-new, no history                   -> instant borrow
"""
import sys
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select, text

from app.core.security import hash_password
from app.db import Base, SessionLocal
from app.models import Activity, Book, Category, Fine, Loan, User

CATEGORIES = {
    "Computer Science": ("Programming, algorithms and software engineering", "#1e3a8a"),
    "Science Fiction": ("Futures, space and technology", "#4c1d95"),
    "Fantasy": ("Magic, myth and other worlds", "#065f46"),
    "Classic Literature": ("Timeless novels", "#7c2d12"),
    "Mystery & Thriller": ("Detectives, crime and suspense", "#111827"),
    "History": ("How the past shaped the present", "#78350f"),
    "Science": ("Physics, biology and the natural world", "#0f766e"),
    "Self-Help & Psychology": ("Habits, minds and decisions", "#9d174d"),
}

# (title, author, category, copies, tags, description)
BOOKS = [
    ("Clean Code", "Robert C. Martin", "Computer Science", 3, ["programming", "craftsmanship", "refactoring"],
     "Principles for writing readable, maintainable code, with many before-and-after examples."),
    ("The Pragmatic Programmer", "Andrew Hunt & David Thomas", "Computer Science", 2, ["programming", "career", "craftsmanship"],
     "Practical advice on becoming a better, more adaptable software developer."),
    ("Introduction to Algorithms", "Cormen, Leiserson, Rivest & Stein", "Computer Science", 2, ["algorithms", "data-structures", "math"],
     "The classic reference textbook on algorithms and their analysis."),
    ("Designing Data-Intensive Applications", "Martin Kleppmann", "Computer Science", 2, ["databases", "distributed-systems", "architecture"],
     "How databases, streams and distributed systems really work, and the trade-offs between them."),
    ("Structure and Interpretation of Computer Programs", "Abelson & Sussman", "Computer Science", 1, ["programming", "lisp", "fundamentals"],
     "A foundational text on abstraction and how programs are built, using Scheme."),
    ("Code: The Hidden Language of Computer Hardware and Software", "Charles Petzold", "Computer Science", 2, ["hardware", "fundamentals", "history"],
     "Builds up how computers work from simple circuits to software, step by step."),
    ("The Mythical Man-Month", "Frederick P. Brooks Jr.", "Computer Science", 1, ["management", "architecture", "career"],
     "Essays on software project management, including why adding people to a late project makes it later."),
    ("Refactoring", "Martin Fowler", "Computer Science", 2, ["refactoring", "programming", "craftsmanship"],
     "A catalogue of techniques for improving the design of existing code safely."),

    ("Dune", "Frank Herbert", "Science Fiction", 3, ["space", "politics", "ecology"],
     "A young heir is caught in a struggle over the desert planet Arrakis and its precious spice."),
    ("Foundation", "Isaac Asimov", "Science Fiction", 2, ["space", "empire", "politics"],
     "A mathematician predicts the fall of a galactic empire and plans to shorten the dark age that follows."),
    ("I, Robot", "Isaac Asimov", "Science Fiction", 2, ["robots", "ai", "ethics"],
     "Linked stories exploring the Three Laws of Robotics and their unexpected consequences."),
    ("Neuromancer", "William Gibson", "Science Fiction", 1, ["cyberpunk", "ai", "hacking"],
     "A washed-up hacker is hired for one last job in a neon-lit cyberspace future."),
    ("The Left Hand of Darkness", "Ursula K. Le Guin", "Science Fiction", 1, ["anthropology", "politics", "identity"],
     "An envoy visits a world whose people have no fixed gender."),
    ("Project Hail Mary", "Andy Weir", "Science Fiction", 2, ["space", "science", "survival"],
     "A lone astronaut wakes up with no memory and must solve a threat to the Sun."),
    ("The Martian", "Andy Weir", "Science Fiction", 2, ["space", "survival", "science"],
     "An astronaut stranded on Mars uses science and humour to stay alive."),
    ("Brave New World", "Aldous Huxley", "Science Fiction", 2, ["dystopia", "society", "control"],
     "A future society kept stable through conditioning, pleasure and engineered castes."),

    ("The Hobbit", "J.R.R. Tolkien", "Fantasy", 3, ["adventure", "dragons", "quest"],
     "Bilbo Baggins is swept into a quest to win back a dwarf kingdom from a dragon."),
    ("The Fellowship of the Ring", "J.R.R. Tolkien", "Fantasy", 2, ["quest", "epic", "friendship"],
     "Frodo sets out to destroy a ring of terrible power."),
    ("Harry Potter and the Philosopher's Stone", "J.K. Rowling", "Fantasy", 3, ["magic", "school", "friendship"],
     "An orphan discovers he is a wizard and begins his studies at Hogwarts."),
    ("A Wizard of Earthsea", "Ursula K. Le Guin", "Fantasy", 1, ["magic", "coming-of-age", "identity"],
     "A gifted young mage unleashes a shadow and must face it."),
    ("The Name of the Wind", "Patrick Rothfuss", "Fantasy", 1, ["magic", "music", "coming-of-age"],
     "A legendary figure tells the true story of his early life."),
    ("Mistborn: The Final Empire", "Brandon Sanderson", "Fantasy", 2, ["magic", "heist", "rebellion"],
     "A street thief joins a crew planning to overthrow an immortal emperor."),
    ("The Lion, the Witch and the Wardrobe", "C.S. Lewis", "Fantasy", 2, ["adventure", "children", "magic"],
     "Four siblings step through a wardrobe into the land of Narnia."),
    ("American Gods", "Neil Gaiman", "Fantasy", 1, ["mythology", "road-trip", "identity"],
     "An ex-convict is drawn into a war between old gods and new ones."),

    ("Pride and Prejudice", "Jane Austen", "Classic Literature", 2, ["romance", "society", "family"],
     "Elizabeth Bennet and Mr Darcy misjudge each other in Regency England."),
    ("1984", "George Orwell", "Classic Literature", 3, ["dystopia", "politics", "control"],
     "Winston Smith lives under a regime that watches everything and rewrites the truth."),
    ("To Kill a Mockingbird", "Harper Lee", "Classic Literature", 2, ["justice", "childhood", "society"],
     "A child watches her father defend a Black man falsely accused in the American South."),
    ("The Great Gatsby", "F. Scott Fitzgerald", "Classic Literature", 2, ["wealth", "romance", "society"],
     "A mysterious millionaire pursues a lost love in 1920s Long Island."),
    ("Crime and Punishment", "Fyodor Dostoevsky", "Classic Literature", 1, ["guilt", "philosophy", "crime"],
     "A poor student commits a murder and is consumed by its consequences."),
    ("Jane Eyre", "Charlotte Bronte", "Classic Literature", 1, ["romance", "independence", "gothic"],
     "An orphaned governess finds love and secrets at Thornfield Hall."),
    ("Frankenstein", "Mary Shelley", "Classic Literature", 2, ["gothic", "science", "ethics"],
     "A scientist creates life and is haunted by what he has made."),
    ("Godaan", "Munshi Premchand", "Classic Literature", 1, ["india", "village", "society"],
     "A poor farmer's life and struggles in rural colonial India."),

    ("The Hound of the Baskervilles", "Arthur Conan Doyle", "Mystery & Thriller", 2, ["detective", "classic", "gothic"],
     "Sherlock Holmes investigates a legendary hound on the moors."),
    ("And Then There Were None", "Agatha Christie", "Mystery & Thriller", 2, ["detective", "island", "suspense"],
     "Ten strangers on an island are killed one by one."),
    ("Murder on the Orient Express", "Agatha Christie", "Mystery & Thriller", 2, ["detective", "train", "classic"],
     "Hercule Poirot solves a murder aboard a snowbound train."),
    ("The Girl with the Dragon Tattoo", "Stieg Larsson", "Mystery & Thriller", 1, ["investigation", "hacking", "crime"],
     "A journalist and a hacker investigate a decades-old disappearance."),
    ("Gone Girl", "Gillian Flynn", "Mystery & Thriller", 1, ["marriage", "suspense", "psychological"],
     "A wife vanishes, and her husband becomes the prime suspect."),
    ("The Da Vinci Code", "Dan Brown", "Mystery & Thriller", 2, ["puzzles", "art", "conspiracy"],
     "A symbologist follows clues hidden in art after a murder at the Louvre."),
    ("The Silent Patient", "Alex Michaelides", "Mystery & Thriller", 1, ["psychological", "suspense", "therapy"],
     "A therapist tries to get a woman who shot her husband to speak again."),
    ("In Cold Blood", "Truman Capote", "Mystery & Thriller", 1, ["true-crime", "investigation", "crime"],
     "A non-fiction account of a 1959 murder in Kansas and its aftermath."),

    ("Sapiens", "Yuval Noah Harari", "History", 3, ["humanity", "civilization", "evolution"],
     "A brief history of humankind from the Stone Age to today."),
    ("Guns, Germs, and Steel", "Jared Diamond", "History", 2, ["civilization", "geography", "empire"],
     "Why some societies came to dominate others, explained through geography and environment."),
    ("SPQR", "Mary Beard", "History", 1, ["rome", "empire", "politics"],
     "A history of ancient Rome from its origins to the third century."),
    ("The Discovery of India", "Jawaharlal Nehru", "History", 2, ["india", "civilization", "culture"],
     "Nehru's survey of Indian history, philosophy and culture, written in prison."),
    ("India After Gandhi", "Ramachandra Guha", "History", 1, ["india", "politics", "democracy"],
     "The story of the world's largest democracy since independence."),
    ("The Silk Roads", "Peter Frankopan", "History", 1, ["trade", "empire", "asia"],
     "World history told from the trade routes that connected East and West."),
    ("The Diary of a Young Girl", "Anne Frank", "History", 2, ["war", "memoir", "holocaust"],
     "The diary of a Jewish girl hiding from the Nazis in Amsterdam."),
    ("The Guns of August", "Barbara W. Tuchman", "History", 1, ["war", "europe", "politics"],
     "The first month of the First World War and the decisions that shaped it."),

    ("A Brief History of Time", "Stephen Hawking", "Science", 3, ["physics", "cosmology", "space"],
     "Black holes, the Big Bang and the nature of time, for general readers."),
    ("Cosmos", "Carl Sagan", "Science", 2, ["space", "astronomy", "curiosity"],
     "A tour of the universe and of how science came to understand it."),
    ("The Selfish Gene", "Richard Dawkins", "Science", 2, ["biology", "evolution", "genetics"],
     "Evolution seen from the point of view of the gene."),
    ("The Gene: An Intimate History", "Siddhartha Mukherjee", "Science", 1, ["genetics", "biology", "history"],
     "The history and future of the gene, mixed with the author's family story."),
    ("Silent Spring", "Rachel Carson", "Science", 1, ["ecology", "environment", "chemistry"],
     "How pesticides harm the natural world; a founding text of environmentalism."),
    ("The Elegant Universe", "Brian Greene", "Science", 1, ["physics", "string-theory", "cosmology"],
     "An accessible introduction to string theory and the search for a unified theory."),
    ("Wings of Fire", "A.P.J. Abdul Kalam", "Science", 3, ["india", "space", "memoir"],
     "Dr Kalam's autobiography, from Rameswaram to India's missile and space programmes."),
    ("Surely You're Joking, Mr. Feynman!", "Richard P. Feynman", "Science", 2, ["physics", "memoir", "curiosity"],
     "Anecdotes from the curious and playful life of a Nobel-winning physicist."),

    ("Atomic Habits", "James Clear", "Self-Help & Psychology", 3, ["habits", "productivity", "behaviour"],
     "Small changes and systems that compound into big results."),
    ("Thinking, Fast and Slow", "Daniel Kahneman", "Self-Help & Psychology", 2, ["decisions", "behaviour", "bias"],
     "Two systems of thought and the biases that shape our judgements."),
    ("Deep Work", "Cal Newport", "Self-Help & Psychology", 2, ["focus", "productivity", "career"],
     "Why focused, distraction-free work is valuable, and how to do more of it."),
    ("Man's Search for Meaning", "Viktor E. Frankl", "Self-Help & Psychology", 2, ["meaning", "memoir", "war"],
     "A psychiatrist's experience in concentration camps and his ideas about finding purpose."),
    ("Mindset", "Carol S. Dweck", "Self-Help & Psychology", 2, ["learning", "growth", "behaviour"],
     "How believing abilities can grow changes how we learn and succeed."),
    ("The Power of Habit", "Charles Duhigg", "Self-Help & Psychology", 1, ["habits", "behaviour", "business"],
     "The science of how habits form and how to change them."),
    ("Ikigai", "Hector Garcia & Francesc Miralles", "Self-Help & Psychology", 2, ["purpose", "longevity", "japan"],
     "Lessons on purpose and long life from Okinawa, Japan."),
    ("Grit", "Angela Duckworth", "Self-Help & Psychology", 1, ["perseverance", "learning", "success"],
     "Why passion and persistence matter more than talent."),
]

STUDENT_PW, LIB_PW = "Student@123", "Librarian@123"


def reset(db) -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    db.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    db.commit()


def seed() -> None:
    db = SessionLocal()
    try:
        if "--reset" in sys.argv:
            reset(db)
        elif db.scalar(select(func.count()).select_from(User)):
            print("Database already has users. Re-run with --reset to wipe and reseed (destroys data).")
            return

        cats = {}
        for name, (desc, _) in CATEGORIES.items():
            cats[name] = Category(name=name, description=desc)
            db.add(cats[name])
        db.flush()

        books = {}
        for title, author, cat, copies, tags, desc in BOOKS:
            books[title] = Book(title=title, author=author, category_id=cats[cat].id, description=desc,
                                tags=tags, total_copies=copies, available_copies=copies,
                                cover_color=CATEGORIES[cat][1])
            db.add(books[title])
        db.flush()

        def user(name, email, role="student"):
            u = User(name=name, email=email, role=role,
                     password_hash=hash_password(LIB_PW if role == "librarian" else STUDENT_PW))
            db.add(u)
            db.flush()
            return u

        lib = user("Priya (Librarian)", "librarian@library.dev", "librarian")
        asha = user("Asha Rao", "asha@library.dev")
        ravi = user("Ravi Kumar", "ravi@library.dev")
        meera = user("Meera Iyer", "meera@library.dev")
        user("Kiran Das", "kiran@library.dev")

        now = datetime.now(timezone.utc)

        def history(student, title, days_ago, days_late=0, returned=True, fine_status=None):
            borrowed = now - timedelta(days=days_ago)
            due = borrowed + timedelta(days=14)
            loan = Loan(user_id=student.id, book_id=books[title].id, status="returned" if returned else "borrowed",
                        requested_at=borrowed, borrowed_at=borrowed, due_at=due,
                        returned_at=due + timedelta(days=days_late) if returned else None)
            db.add(loan)
            db.flush()
            if not returned:
                books[title].available_copies -= 1
            if returned and days_late > 0:
                db.add(Fine(loan_id=loan.id, user_id=student.id, days_late=days_late, amount=days_late * 5,
                            status=fine_status or "unpaid",
                            paid_at=(due + timedelta(days=days_late + 1)) if fine_status == "paid" else None))
            db.add(Activity(user_id=student.id, action="loan.seeded", entity="loan", entity_id=loan.id,
                            details={"title": title}))

        # Asha: sci-fi + science fan, always on time, one book out now (not overdue)
        for t, d in [("Dune", 120), ("Foundation", 95), ("Cosmos", 70), ("The Martian", 45)]:
            history(asha, t, d)
        history(asha, "Project Hail Mary", 5, returned=False)
        # Ravi: CS + history, two late returns with unpaid fines -> approval
        history(ravi, "Clean Code", 100, days_late=3)
        history(ravi, "Sapiens", 60, days_late=4)
        history(ravi, "Refactoring", 40)
        # Meera: mystery reader, late + currently overdue -> blocked
        history(meera, "And Then There Were None", 90, days_late=6, fine_status="paid")
        history(meera, "Gone Girl", 70, days_late=8)
        history(meera, "The Silent Patient", 30, returned=False)  # due 16 days ago -> overdue
        history(meera, "The Da Vinci Code", 50, days_late=2)
        # Co-borrowing signal so "readers also borrowed" has data
        history(ravi, "Dune", 20)
        db.add(Activity(user_id=lib.id, action="seed.completed", entity="system", entity_id=None, details={}))
        db.commit()
        print(f"Seeded {len(CATEGORIES)} categories, {len(BOOKS)} books, 5 users with loan history.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
