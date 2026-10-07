-- Runs once, the first time the Postgres volume is created.
-- pgvector in the main DB (the Alembic migration also does this; harmless to repeat).
CREATE EXTENSION IF NOT EXISTS vector;

-- A separate database for pytest so tests never touch your real data.
CREATE DATABASE lms_test;
\c lms_test
CREATE EXTENSION IF NOT EXISTS vector;
