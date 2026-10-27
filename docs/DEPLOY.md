# Deploying Reading Room (sandbox / any public URL)

Team standards: **pnpm** for the frontend, and **no Docker for anything we deploy**. The
`docker-compose.yml` database is a local-dev convenience only.

## Before any public URL: checklist

| | Item | Why |
|:-:|:--|:--|
| ☐ | `LMS_COOKIE_SECURE=true` and the site served over HTTPS | Otherwise the browser sends the auth cookie over plain http |
| ☐ | A real `LMS_JWT_SECRET` (`python -c "import secrets; print(secrets.token_hex(32))"`) | Anyone with the secret can mint tokens |
| ☐ | uvicorn runs with `--proxy-headers --forwarded-allow-ips=<proxy ip>` | Without it every request looks like it comes from the proxy, so the login rate limit locks out everyone together |
| ☐ | Exactly **one** uvicorn worker | The login rate limiter counts in memory per process (`services/rate_limit.py`). More workers or hosts need a shared store first |
| ☐ | `LMS_CORS_ORIGINS` = the real site origin only | Credentials are allowed for these origins |
| ☐ | Frontend and `/api` on the **same site** (one domain, reverse proxy) | The cookie is `SameSite=Lax`; a different site would not get it |
| ☐ | `alembic upgrade head` run against the server DB | Schema |
| ☐ | Postgres port not exposed publicly (bind localhost / private network) | See LMS-BUG-007 |

## Database: native PostgreSQL 16 + pgvector

Ubuntu/Debian with the PostgreSQL apt repository ([PGDG](https://wiki.postgresql.org/wiki/Apt)):

```bash
sudo apt install postgresql-16 postgresql-16-pgvector
sudo -u postgres psql -c "CREATE ROLE lms LOGIN PASSWORD '<strong password>';"
sudo -u postgres psql -c "CREATE DATABASE lms OWNER lms;"
sudo -u postgres psql -d lms -c "CREATE EXTENSION IF NOT EXISTS vector;"   # needs superuser, so do it here
```

`CREATE EXTENSION` needs a superuser, so run it as `postgres` before the first migration. The Alembic
migration's own `CREATE EXTENSION IF NOT EXISTS` is then a no-op. A test database (`lms_test`) is only
needed where pytest runs, not on the server.

Windows dev machines without Docker: install PostgreSQL 16 from the EDB installer and build pgvector
following [pgvector's Windows instructions](https://github.com/pgvector/pgvector#windows), then point
`LMS_DATABASE_URL` at it. `backend/run.sh` uses any database already listening on the URL's host:port;
`LMS_NO_DOCKER=1 ./run.sh` makes it refuse to fall back to Docker.

## Frontend build

```bash
cd frontend
pnpm install --frozen-lockfile     # or: corepack pnpm ... (version pinned in package.json)
pnpm run build                     # static files in dist/, serve them behind the same reverse proxy as /api
```
