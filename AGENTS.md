# Repository Guidelines

## Project Structure & Module Organization
- `main.py` bootstraps FastAPI, loads environment variables, and mounts the LINE login router from `app/modules/line_login/`.
- Core LINE helpers live in `app/line_login.py`; share-only code should stay here so HTTP handlers remain thin.
- Additional domain models belong in `app/models.py`; keep new routers in `app/modules/<feature>/` with an `__init__.py` that exposes `router`.
- Static client assets are served from `static/`, while automated tests mirror module names under `test/` (e.g., `test_line_login.py`).
- Database migrations are managed by `alembic/` and configured via `alembic.ini`.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` — install runtime and test dependencies.
- `uvicorn main:app --reload` — start the FastAPI dev server with auto-reload.
- `pytest` — run the full test suite; ensure it passes before pushing.
- `alembic revision --autogenerate -m "<note>"` followed by `alembic upgrade head` — create and apply schema migrations.

## Coding Style & Naming Conventions
- Follow PEP 8 basics: four-space indentation, snake_case for functions and variables, PascalCase for classes.
- 註解使用繁體中文並解依照Python PEP 257 docstring格式。
- Keep module-level constants uppercase and grouped logically (see `app/line_login.py`).
- Prefer explicit imports (`from app.modules.line_login import router`) and avoid wildcard imports.
- Add short comments only for non-obvious logic (e.g., nonce fallback handling in `router.py`).

## Testing Guidelines
- Use `pytest` with plain `assert` statements; async workflows should use `asyncio.run` within tests when needed.
- Name files `test_<module>.py` and functions `test_<behavior>`; store fixtures alongside related tests.
- Cover both success and failure paths (cookies missing, JWKS refresh, etc.) and add targeted regression tests when fixing bugs.

## Commit & Pull Request Guidelines
- Write imperative commit messages (e.g., `Add LINE login router cache`); keep each commit focused on one concern.
- Pull requests should describe motivation, summarize changes, list verification steps (`pytest`, manual scenarios), and link related issues.
- Include screenshots or terminal output when altering user-facing flows or operational scripts.

## Security & Configuration Tips
- Never commit secrets: keep `.env` out of version control and update `README.md` when new environment variables are required.
- Validate external calls with the built-in `httpx` client defaults (10s timeout) and reuse JWKS caching to avoid rate limits.
- Set cookies with `secure=True` and `SameSite=None` for production HTTPS deployments; adjust `.env` overrides cautiously.
# Repository Guidelines

## Project Structure & Module Organization
- Entry: `main.py` bootstraps FastAPI, loads `.env`, mounts routers.
- Core LINE helpers: `app/line_login.py` (shared logic; keep handlers thin).
- Models and DB schema: `app/models.py` with Alembic migrations under `alembic/`.
- Routers per feature: `app/modules/<feature>/` exposing `router`.
  - LINE Login: `app/modules/line_login/router.py`
  - Menu API: `app/modules/menu/router.py` (service in `menu.py`)
- Frontend (Vite + Vue): `static/` (dev sources), build output in `static/dist/`.
- Tests: `test/` (mirrors module names; e.g., `test_line_login.py`).

## Build, Test, and Development Commands
- Backend deps: `pip install -r requirements.txt`
- Run API (reload): `uvicorn main:app --reload`
- Tests: `pytest`
- DB migrations: `alembic revision --autogenerate -m "<note>" && alembic upgrade head`
- Frontend dev: `cd static && npm ci && npm run dev`
- Frontend build: `cd static && npm ci && npm run build` (served from `static/dist/`).

## Coding Style & Naming Conventions
- Python: PEP 8 (4 spaces), `snake_case` for funcs/vars, `PascalCase` for classes.
- Docstrings follow PEP 257; brief comments in 繁體中文對於非直覺邏輯。
- Constants UPPERCASE and grouped (see `app/line_login.py`).
- Prefer explicit imports: `from app.modules.line_login import router`.

## Testing Guidelines
- Framework: `pytest` with plain `assert`.
- Naming: files `test_<module>.py`, functions `test_<behavior>`.
- Coverage: include success and failure paths (e.g., cookies missing, JWKS refresh).
- Async flows: wrap with `asyncio.run(...)` in tests when needed.

## Commit & Pull Request Guidelines
- Commits: imperative mood, one concern per commit (e.g., `Add LINE login router cache`).
- PRs: describe motivation, summarize changes, list verification steps (`pytest`, manual flows), and link issues.
- Include screenshots or terminal output for user-facing or operational changes.

## Security & Configuration Tips
- Do not commit secrets; keep `.env` out of VCS. Use `DATABASE_URL` or `DB_*` in `.env`.
- Alembic reads `DATABASE_URL` from `.env`; API uses the same engine settings.
- External calls: use `httpx` defaults (10s timeout) and reuse JWKS caching.
- Cookies for production: `secure=True`, `SameSite=None`; adjust via `.env`.

## Agent-Specific Notes
- Keep domain logic in shared modules (`app/line_login.py`, `app/modules/menu/menu.py`).
- Routers should be thin: parse inputs, call services, shape responses.
- Do not rename files or refactor across modules unless required by the task; prefer minimal, targeted diffs.
