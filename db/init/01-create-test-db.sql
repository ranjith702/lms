-- Runs once, the first time the Postgres volume is created.
-- A separate database for pytest so tests never touch your real data.
CREATE DATABASE lms_test;
