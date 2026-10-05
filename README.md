# Hyro hiring research service

Copy `.env.example` to `.env`, replace the local credentials, then run `docker compose up --build`. FastAPI is at `http://localhost:3000/docs`; Temporal UI is at `http://localhost:8080`.

The API and worker apply application Alembic migrations on startup. Temporal's auto-setup container manages its own schemas in separate PostgreSQL databases. The seeded development user is `SEED_USER_EMAIL`; authentication is not part of this local v1.

Typical flow: create a project; POST a rough JD to `/projects/{id}/jds`; POST `/projects/{id}/jds/{jd_id}/criteria`; optionally PUT edits to `/projects/{id}/criteria/{criteria_id}`; POST its `/approve` endpoint; POST `/projects/{id}/runs`; poll `/projects/{id}/runs/{run_id}`; fetch `/results` and save decisions.

For host-side commands, set `DATABASE_URL` to use `localhost` instead of the Compose hostname `postgres`. Run tests with `pip install -e '.[test]' && pytest`.

The research UI is at `http://localhost:3000/app/`. It reads and writes through the FastAPI endpoints; no candidate records are embedded in the frontend. Upload accepts plain `.txt` files and reads them locally before submitting the JD text. The page polls run status and loads paginated results after completion. The current run API reports only queued, running, completed, or failed, so the progress display reflects those states rather than activity-level progress.
