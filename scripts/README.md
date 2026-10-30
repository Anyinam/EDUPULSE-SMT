# Scripts

One-off maintenance and diagnostic scripts. None of these are part of the
production image (`backend/Dockerfile` only copies `backend/` and `alembic/`).

Run them from the repository root so `backend` is importable:

```bash
PYTHONPATH=. python scripts/maintenance/<script>.py
```

- `maintenance/` – data backfills, manual migrations, onboarding and admin helpers.
  Most touch the database directly; read a script before running it against a real environment.
- `manual_checks/` – ad-hoc verification scripts (not collected by pytest; the real suite lives in `tests/`).

Load testing lives in `tools/locustfile.py`; sample import files live in `samples/`.
