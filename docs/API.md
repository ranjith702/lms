# API reference

Generated from the running server's OpenAPI schema (`/openapi.json`). Interactive docs: http://127.0.0.1:8000/docs

Auth: send `Authorization: Bearer <access_token>` from `POST /api/auth/login`. Routes under *people & insights*, `GET /api/loans`, `/api/fines` (list/pay/waive), approve/reject, and book/category writes need the **librarian** role (students get 403).

Errors are JSON: `{"detail": "message"}` (validation errors: a list of field problems).

| Group | Method | Path | Access | Summary |
|---|---|---|---|---|
| auth | GET | `/api/auth/me` | login | Me |
| auth | GET | `/api/auth/me/sessions` | login | My Sessions |
| auth | GET | `/api/auth/me/trust` | login | My Trust |
| auth | POST | `/api/auth/login` | public | Login |
| auth | POST | `/api/auth/logout` | login | Logout |
| auth | POST | `/api/auth/register` | public | Register |
| catalog | DELETE | `/api/books/{book_id}` | login | Delete Book |
| catalog | GET | `/api/books` | login | List Books |
| catalog | GET | `/api/books/{book_id}` | login | Get Book |
| catalog | GET | `/api/categories` | login | List Categories |
| catalog | POST | `/api/books` | login | Create Book |
| catalog | POST | `/api/categories` | login | Create Category |
| catalog | PUT | `/api/categories/{category_id}` | login | Update Category (rename re-embeds its books; 409 on duplicate name) |
| catalog | DELETE | `/api/categories/{category_id}` | login | Delete Category (409 while it still has books) |
| catalog | PUT | `/api/books/{book_id}` | login | Update Book |
| health | GET | `/api/health` | public | Health |
| loans & fines | GET | `/api/fines` | login | All Fines |
| loans & fines | GET | `/api/fines/me` | login | My Fines |
| loans & fines | GET | `/api/loans` | login | All Loans |
| loans & fines | GET | `/api/loans/me` | login | My Loans |
| loans & fines | POST | `/api/fines/{fine_id}/pay` | login | Pay |
| loans & fines | POST | `/api/fines/{fine_id}/waive` | login | Waive |
| loans & fines | POST | `/api/loans` | login | Borrow |
| loans & fines | POST | `/api/loans/{loan_id}/approve` | login | Approve |
| loans & fines | POST | `/api/loans/{loan_id}/reject` | login | Reject |
| loans & fines | POST | `/api/loans/{loan_id}/return` | login | Return Book |
| people & insights | GET | `/api/activity` | login | Activity Feed |
| people & insights | GET | `/api/activity/me` | login | My Activity |
| people & insights | GET | `/api/dashboard` | login | Dashboard |
| people & insights | GET | `/api/recommendations/me` | login | My Recommendations |
| people & insights | GET | `/api/users/students` | login | Students |
| people & insights | GET | `/api/users/{user_id}/insights` | login | Insights |
| people & insights | POST | `/api/assistant/ask` | login | Ask |

Total: 31 endpoints.
