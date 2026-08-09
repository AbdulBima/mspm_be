# Sprint Ops API

An open-source backend for sprint and team-operations tracking: sprint and
goal tracking, task management, daily check-ins, standup attendance, a
risk/blocker register, meeting notes, PDF exports, an AI assistant, and
leadership-facing report generation.

It's a standalone service — its own database, its own auth, its own deploy
— so it's straightforward to run on its own or adapt into a larger system.

## Status

This project started as an internal tool and is now released as open
source. Issues and pull requests are welcome — see [Contributing](#contributing)
below.

## Stack

- FastAPI + Motor (async MongoDB driver)
- Pydantic v2 / pydantic-settings for validated configuration
- JWT auth (python-jose) over a single manager/RPM account class
- ReportLab for server-side PDF generation
- Groq (Llama) for optional AI narrative generation — additive only; every
  endpoint that uses it still returns full structured data if it's
  unconfigured or the call fails

## Project layout

    app/
      main.py              # application factory + lifespan
      core/                # settings, security (JWT/password), logging
      db/                  # Motor client, collection handles, indexes
      schemas/             # Pydantic request contracts, one module per domain
      services/            # business logic: dates, task flags, alignment,
                            # burndown, commitment classification, the AI
                            # narrative wrapper, PDF builders (services/pdf/)
      api/v1/               # route handlers, one module per domain
    tests/                 # pytest suite
    main.py                # thin process entrypoint (`uvicorn main:app`)

## Running locally

    cp .env.example .env   # fill in MONGO_URI and SECRET_KEY at minimum
    pip install -r requirements-dev.txt
    uvicorn main:app --reload --port 8000

`/docs` and `/redoc` are only mounted when `ENV=development`.

## Running in production

    uvicorn main:app --host 0.0.0.0 --port $PORT --workers 4

`GET /health` returns `200` with `{"status": "ok", ...}` when the database
is reachable, and `503` with `{"status": "degraded", ...}` otherwise — wire
this into your load balancer's / orchestrator's readiness probe.

## Tests

    pytest

The suite covers pure business logic (task flags, sprint calendar math,
standup-commitment classification) and the unauthenticated health/root
endpoints. It does not require a live MongoDB instance — the DB calls made
during app startup are mocked in `tests/conftest.py`.

## Linting / formatting / types

    ruff check .
    black --check .
    mypy app

## API surface

Routes are grouped by domain under `app/api/v1/` (auth, sprints, members,
tasks, tracking, reports, ai), each declaring its own path prefix — see the
relevant module for the exact paths it exposes.

## Frontend

This API is consumed by a companion Next.js frontend (not part of this
repo) — see that project's own README for its structure and setup.

## Contributing

Contributions are welcome. Before opening a pull request, please make sure
the full check suite passes:

    pytest
    ruff check .
    black --check .
    mypy app

A few conventions worth knowing before you dig in:

- Business logic belongs in `app/services/`, not in the route handlers —
  route modules should stay thin (parse request, call a service, shape the
  response).
- MongoDB collections are handled through `app/db/collections.py`; don't
  reach for `motor` directly elsewhere.
- Keep PRs focused. A PR that fixes one thing is much easier to review than
  one that bundles several unrelated changes.

If you're planning a larger change, opening an issue first to discuss the
approach is appreciated.

## License

MIT — see [LICENSE](LICENSE).
