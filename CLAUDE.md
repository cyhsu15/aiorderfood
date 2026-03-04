# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

AIOrderFood is a FastAPI-based restaurant ordering system with LINE Login authentication, menu management, shopping cart, and order processing. The backend uses PostgreSQL with SQLAlchemy ORM and Alembic migrations. The frontend is built with Vue 3 + Vite and can run in dev mode (Vite dev server) or production mode (built and served by FastAPI).

### Core Components

- **Authentication**: LINE Login OAuth flow with JWT session management (`app/line_login.py`, `app/modules/line_login/`)
- **Menu System**: Category-based menu with dishes, prices, translations, and set meals (`app/modules/menu/`)
- **Order Processing**: Shopping cart stored in database sessions, order creation and management (`app/modules/order/`)
- **Session Management**: Server-side session storage in PostgreSQL for anonymous users (`app/session.py`)
  - Supports shared table sessions via URL parameters (`?sessionid={GUID}&tableid={label}`)
- **Real-time Sync (SSE)**: Server-Sent Events for multi-user cart synchronization (`app/modules/sse/`)
- **QR Code Generation**: Dynamic QR code generation for shared table ordering (`app/modules/qrcode/`)
- **Database Layer**: SQLAlchemy with connection pooling and dependency injection (`app/db.py`)

### Key Patterns

1. **Module Organization**: Features are organized under `app/modules/<feature>/` with each exposing a `router` via `__init__.py`. Business logic lives in separate service files (e.g., `menu.py`, `service.py`).

2. **Database Access**: All routes use `db: Session = Depends(get_db)` for dependency injection. Service functions receive the Session and perform queries. Use SQLAlchemy Core (text queries with `.mappings()`) for reads and ORM for writes.

3. **Frontend Integration**: FastAPI serves two frontends:
   - Vue SPA in `static/dist/` (production build)
   - Vanilla JS admin UI in `static/admin/` (served at `/admin`)
   - Dev mode fallback to `static/index.html` when dist doesn't exist

4. **Session Pattern**: `ensure_session(request, response, db)` in `app/session.py` provides or creates a UserSession, automatically setting cookies for anonymous users.

## Development Commands

### Python Environment

**Required:** Python 3.11.13 (recommended) or Python 3.11+

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (default: http://127.0.0.1:8000)
uvicorn main:app --reload

# Run all tests
pytest

# Run specific test file
pytest test/test_menu.py

# Run specific test function
pytest test/test_menu.py::test_category_crud

# Run tests with verbose output
pytest -v

# Run tests with output capture disabled (see print statements)
pytest -s

# Run E2E tests (fully automated - no manual server startup required)
pytest test/e2e/ --headed

# Run E2E tests in headless mode
pytest test/e2e/

# Run specific E2E test
pytest test/e2e/tests/test_menu_browsing.py::test_menu_page_loads_successfully --headed

# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head
alembic downgrade -1

# Import menu data
python tool/menu_db.py
```

### Frontend (Vue SPA)

```bash
# Development mode (Vite dev server at localhost:5173)
cd static && npm ci && npm run dev

# Production build (served by FastAPI at /)
cd static && npm ci && npm run build
```

### Database Setup

**Using Docker:**
```bash
# Create PostgreSQL container
docker run --name postgres -e POSTGRES_PASSWORD=<pass> -p 5432:5432 -v postgres_data:/var/lib/postgresql/data -d postgres

# Create pgAdmin container
docker run -d --name pgadmin -p 11111:80 -e PGADMIN_DEFAULT_EMAIL=admin@gmail.com -e PGADMIN_DEFAULT_PASSWORD=<pass> -v pgadmin_data:/var/lib/pgadmin dpage/pgadmin4
```

**Windows PowerShell Environment Variables:**
```powershell
# Set DATABASE_URL for Alembic
$env:DATABASE_URL="postgresql+psycopg2://USER:PASS@HOST:PORT/DB"
alembic upgrade head
```

## Database Schema

### Menu Tables
- `category`: Menu categories with sort_order
- `dish`: Dishes with category_id, is_set flag, sort_order
- `dish_price`: Multiple prices per dish (e.g., small/medium/large)
- `dish_translation`: Multi-language names and descriptions
- `dish_detail`: Extended dish information (image_url, description, tags)
- `set_item`: Set meal composition (many-to-many dish relationships)

### Order Tables
- `user_session`: Session storage with JSON data field for cart, table_id for shared sessions
- `orders`: Order header with status, contact info, cart_snapshot, table_id (copied from session)
- `order_item`: Order line items with snapshots of dish data

### Relationships
- Category → Dishes (one-to-many)
- Dish → Prices, Translations, Detail (one-to-many/one-to-one)
- Dish → SetItems (self-referential for set meals)
- UserSession → Orders (one-to-many)
- Order → OrderItems (one-to-many)

## Configuration

Environment variables are loaded from `.env` (copy from `.env.example`):

### LINE Login
- `LINE_CHANNEL_ID`, `LINE_CHANNEL_SECRET`: LINE Developer Console credentials
- `LINE_REDIRECT_URI`: OAuth callback URL (must match LINE console)
- `LIFF_ID`: LINE Frontend Framework ID

### Database
- `DATABASE_URL`: Full connection string (preferred)
  - Format: `postgresql+psycopg2://USER:PASS@HOST:PORT/DBNAME`
- Alternative: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, `DB_NAME`
- `TEST_DATABASE_URL`: Separate test database (must contain "ai_order_food_test" in name)

### Session Cookies
- `CART_SESSION_COOKIE_NAME`: Cookie name for session ID (default: cart_session_id)
- `CART_SESSION_COOKIE_MAX_AGE`: Cookie lifetime in seconds (default: 21600 / 6 hours)
- `COOKIE_SECURE`: Enable secure flag for HTTPS (default: true)

## Testing

The project has two types of tests: **Unit/Integration Tests** and **E2E (End-to-End) Tests**.

### Unit/Integration Tests

Tests use pytest with a dedicated test database. The `test/conftest.py` fixture:
1. Verifies TEST_DATABASE_URL points to a test database (must contain "ai_order_food_test")
2. Runs Alembic migrations to head before test session
3. Truncates all tables between tests (preserving alembic_version)
4. Provides `db` fixture for each test (yields SQLAlchemy Session)

**Test Structure:**
- Test files mirror module structure: `test_line_login.py`, `test_menu.py`, `test_order.py`, `test_chat.py`
- New feature tests: `test_shared_session.py` (shared table ordering), `test_qrcode.py` (QR code generation)
- Each test file imports from `conftest.py` for database fixtures
- Tests use `TestClient` from FastAPI for API endpoint testing
- Use `db.execute(text("..."))` for direct SQL assertions

**Test Coverage:**
- Total: 92 unit/integration tests
- QR Code: 15 tests (100% pass without database)
- Shared Session: 11 tests (require database)
- Known Issue: Alembic encoding error on Windows (cp950 codec) blocks database-dependent tests

**Running Unit/Integration Tests:**
```bash
# Run one test function
pytest test/test_order.py::test_cart_session_persistence

# Run all tests in a file
pytest test/test_menu.py -v

# Run tests matching a pattern
pytest -k "cart" -v
```

### E2E Tests (Fully Automated)

E2E tests use Playwright for browser-based testing. **No manual server startup required** - the test framework automatically:
1. Loads `.env` file and environment variables
2. Builds the frontend (`npm run build`)
3. Starts the test server with `TEST_MODE=1`
4. Runs all E2E tests in a real browser
5. Shuts down the server and cleans up

**Test Infrastructure:**
- `test/e2e/config.py`: Centralized configuration (server port, timeouts, build options)
- `test/e2e/frontend_builder.py`: Automated frontend build management
- `test/e2e/server_manager.py`: Test server lifecycle management (subprocess-based)
- `test/e2e/conftest.py`: Pytest fixtures with auto-startup/shutdown
- `test/e2e/RUNNING_TESTS.md`: Detailed usage guide and troubleshooting

**Test Coverage:**
- Total: 17 E2E tests
- Menu browsing: 5 tests
- Cart operations: 7 tests
- Shared session (multi-user): 5 tests

**Running E2E Tests:**
```bash
# Run all E2E tests with visible browser (one command!)
pytest test/e2e/ --headed

# Run in headless mode
pytest test/e2e/

# Run specific test
pytest test/e2e/tests/test_menu_browsing.py::test_menu_page_loads_successfully --headed

# Slow motion for debugging
pytest test/e2e/ --headed --slowmo 1000
```

**Key Features:**
- ✅ **Zero manual setup**: Just run `pytest test/e2e/`
- ✅ **Auto frontend build**: Runs `npm run build` before tests
- ✅ **Auto server startup**: Launches uvicorn with test database
- ✅ **Health check**: Ensures server is ready before running tests
- ✅ **Log capture**: Server logs saved to temp files for debugging
- ✅ **Graceful shutdown**: Cleans up resources after tests

**Requirements:**
- Playwright browsers installed: `playwright install chromium`
- E2E dependencies: `pip install -r test/e2e/requirements.txt`
- Frontend dependencies: `cd static && npm ci`
- Test database configured in `.env`: `TEST_DATABASE_URL=...`

## API Routes

### Public APIs
- `GET /api/menu`: Fetch complete menu with categories, dishes, prices, set items
- `GET /api/cart`: Get current session cart
  - Supports `?sessionid={UUID}&tableid={label}` for shared table ordering
- `PUT /api/cart`: Replace cart contents (broadcasts via SSE)
- `DELETE /api/cart`: Clear cart
- `POST /api/orders`: Create order from cart (broadcasts via SSE)
- `GET /api/sse/cart/{session_id}`: SSE endpoint for real-time cart updates

### Admin APIs
- `GET /api/admin/categories`: List categories
- `POST /api/admin/categories`: Create category
- `PATCH /api/admin/categories/{id}`: Update category (supports sort_order)
- `DELETE /api/admin/categories/{id}`: Delete category
- `GET /api/admin/dishes`: List dishes by category
- `POST /api/admin/dishes`: Create dish with prices/translations/detail
- `PATCH /api/admin/dishes/{id}`: Update dish
- `DELETE /api/admin/dishes/{id}`: Delete dish
- `GET /api/admin/orders`: List recent orders
- `GET /api/admin/orders/{id}`: Get order detail
- `PATCH /api/admin/orders/{id}`: Update order status/items
- `GET /api/admin/sessions`: List user sessions
- `GET /api/admin/sessions/{id}`: Get session detail with cart
- `POST /api/admin/sessions/{id}/clear-cart`: Clear session cart
- `DELETE /api/admin/sessions/{id}`: Delete session
- `GET /api/admin/qrcode/generate`: Generate table QR code (JSON format with base64 image)
  - Params: `tableid` (required), `sessionid` (optional, auto-generates UUID if not provided)
- `GET /api/admin/qrcode/image`: Generate table QR code (PNG image)
  - Params: `tableid` (required), `sessionid` (optional)

### Authentication
- `GET /auth/line/login`: Initiate LINE OAuth flow
- `GET /auth/line/callback`: OAuth callback handler

## Shared Table Ordering (Multi-User Feature)

The system supports multiple users ordering from the same table simultaneously using a shared session.

### How It Works

1. **QR Code Generation** (`/admin/qrcode.html`):
   - Admin generates a QR code with unique `sessionid` (UUID) and `tableid` (display label like "A1", "B2")
   - QR code contains URL: `https://example.com/?sessionid={UUID}&tableid={label}`

2. **Session Initialization**:
   - Users scan QR code, landing page extracts URL parameters
   - Frontend (`static/src/stores/session.js`) saves to localStorage and cleans URL
   - All API calls automatically include session parameters via cookies

3. **Real-Time Synchronization**:
   - Frontend connects to SSE endpoint `/api/sse/cart/{session_id}`
   - Server broadcasts cart updates, order status changes, version conflicts
   - All users at the same table see changes instantly

4. **Optimistic Locking**:
   - Cart includes `version` field (incremented on each update)
   - PUT `/api/cart` with stale version returns 409 Conflict
   - Frontend auto-merges changes and retries

5. **Empty Cart Protection**:
   - After first order submitted, cannot submit empty cart (`cannot_submit_empty_cart_after_order`)
   - Prevents accidental empty orders while allowing追加訂單 (additional orders)

### Key Implementation Details

- **Backend**: `app/session.py` handles `sessionid` and `tableid` URL parameters
- **Frontend Session Store**: `static/src/stores/session.js` manages shared state
- **Frontend Cart Store**: `static/src/stores/cart.js` handles SSE connection and conflicts
- **SSE Manager**: `app/modules/sse/service.py` with connection pooling and broadcasting
- **Database**: `user_session.table_id` and `orders.table_id` track table associations

### SSE Event Types

- `connected`: Confirms SSE connection established
- `cart_updated`: Cart changed by another user
- `order_status_updated`: Order status changed or new order created
- `version_conflict`: Version mismatch detected
- `keepalive`: Heartbeat to maintain connection

### Admin Tools

- **QR Code Generator** (`/admin/qrcode.html`): Generate and download/print table QR codes
- **Session Management**: View active sessions and their table assignments

## Coding Conventions

- **Python Style**: PEP 8 with 4-space indentation, snake_case functions/variables, PascalCase classes
- **Docstrings**: PEP 257 format, may use 繁體中文 for domain-specific comments
- **Imports**: Explicit imports preferred, avoid wildcards
- **Service Layer**: Keep routers thin (parse input, call service, return response). Business logic in service modules.
- **Error Handling**: Services raise `ValueError` with error codes, routers convert to HTTPException with appropriate status codes

## Common Patterns

### Adding a New Feature Module

1. Create `app/modules/<feature>/` directory
2. Add `router.py` with FastAPI router
3. Add `service.py` for business logic
4. Export router in `__init__.py`: `from .router import router`
5. Mount in `main.py`: `app.include_router(<feature>_router, prefix="/api")`
6. Create migration if database changes needed
7. Add test file: `test/<feature>.py`

### Database Query Pattern

```python
# Service function
def fetch_items(db: Session) -> List[Dict]:
    rows = db.execute(text("SELECT ...")).mappings().all()
    return [dict(r) for r in rows]

# Router
@router.get("/items")
def list_items(db: Session = Depends(get_db)):
    return fetch_items(db)
```

### Session-Based Cart Access

```python
from app.session import ensure_session

@router.get("/cart")
def get_cart(request: Request, response: Response, db: Session = Depends(get_db)):
    session, created = ensure_session(request, response, db)
    cart_data = session.data.get("cart", {})
    return cart_data
```

## Migration Workflow

Alembic reads `DATABASE_URL` from `.env` (see `alembic/env.py`). Models are defined in `app/models.py` with SQLAlchemy declarative base.

```bash
# Auto-generate migration from model changes
alembic revision --autogenerate -m "add new_field to table"

# Review generated migration in alembic/versions/
# Edit if needed (e.g., data migrations, custom constraints)

# Apply migration
alembic upgrade head

# Rollback one revision
alembic downgrade -1
```

Migration naming convention: `YYYYMMDD_NN_description.py` (e.g., `20251021_02_add_session_and_order_tables.py`)

## Important Notes

- **Table Names**: PostgreSQL lowercases unquoted identifiers. All table names use snake_case lowercase.
- **Cascade Deletes**: Models use appropriate cascade settings. Dish deletion is protected if used in sets (`RESTRICT` on `SetItem.item_id`).
- **Price Storage**: Uses `Numeric(12, 2)` for monetary values to avoid floating-point precision issues.
- **Cart Snapshot**: Orders store `cart_snapshot` JSON to preserve state even if menu items are later modified/deleted.
- **Connection Pool**: Default pool size is 5 with max_overflow 5, pool_recycle 1800s. Adjust via env vars if needed.
- **Test Database Safety**: Tests require database name containing "ai_order_food_test" to prevent accidental data loss.

## Dependency Management

The project uses a minimal `requirements.txt` with only essential packages:

**Core Dependencies:**
- `httpx`: Serves dual purpose (LINE Login API calls + FastAPI TestClient dependency)
- `psycopg2-binary`: For development/testing only; consider using `psycopg2` in production for better performance
- `uvicorn[standard]`: Includes uvloop, httptools, and watchfiles for optimal performance
- `qrcode[pil]==8.0`: QR code generation for shared table ordering
- `Pillow==11.1.0`: Image processing library (required by qrcode)

**Optional Dependencies (commented out):**
- `selenium` and `beautifulsoup4`: Only needed for `tool/dish_describer/` web scraping scripts

When adding new dependencies:
1. Add to `requirements.txt` with pinned version
2. Include inline comment if purpose is not obvious
3. Group by category (FastAPI core, Database, Authentication, etc.)

## Tools and Utilities

- `tool/menu_db.py`: Import menu data from external sources
- `tool/dish_describer/`: Selenium-based tools for scraping dish descriptions from restaurant websites

## Troubleshooting

### Frontend Issues

**404 on `/src/main.js`:**
- Cause: Accessing development `index.html` through FastAPI without Vite dev server running
- Solution: Either run `npm run build` (production) or `npm run dev` (development with Vite)

**`/api/menu` returns empty:**
- Check database table names are lowercase with underscores (`category`, `dish`, `dish_price`, `dish_translation`)
- Ensure Alembic migrations are applied: `alembic upgrade head`
- Verify menu data is imported: `python tool/menu_db.py`

**Frontend can't reach backend API:**
- Development mode: Check `vite.config.js` proxy points to correct backend port (default: `http://localhost:3000`)
- Production mode: Ensure `static/dist/` exists and backend is serving it

### Database Issues

**Alembic can't connect:**
- Verify `.env` file exists with `DATABASE_URL` or individual `DB_*` variables
- Check PostgreSQL is running (Docker: `docker ps`)
- Test connection: `psql $DATABASE_URL`

**Tests fail with connection error:**
- Ensure `TEST_DATABASE_URL` is set in `.env`
- Database name must contain "ai_order_food_test" for safety
- Create test database if it doesn't exist
