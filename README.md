# CampusBridge

CampusBridge is a responsive university networking prototype for students, faculty, and alumni. The interface follows the provided screen designs and the project report's role-based requirements. It uses React, FastAPI, and PostgreSQL.

## Run the application

The simplest setup uses Docker Compose. Copy `.env.example` to `.env`, set a long random `SECRET_KEY`, then run:

```sh
docker compose up --build
```

Open [http://localhost:5173](http://localhost:5173). The API is available at [http://localhost:8000](http://localhost:8000), with interactive API documentation at [http://localhost:8000/docs](http://localhost:8000/docs).

The first API startup creates the PostgreSQL tables and inserts clearly marked demo records. The compose configuration is for local development; change the development database password, secret, CORS settings, and deployment configuration before hosting the service.

### PostgreSQL data and schema

Docker Compose runs PostgreSQL 16 in the `database` service. FastAPI connects to it at `database:5432` on Compose's private network. The database files are kept in the named Docker volume `campusbridge-data`, not in a source-code folder. The PostgreSQL engine and session are configured in `backend/app/database/connection.py`, and ORM models are in `backend/app/database/models.py`. The API creates the tables at startup. To inspect the database, run:

```sh
docker compose exec database psql -U campusbridge -d campusbridge
```

`docker compose down` stops the containers and preserves the database volume. The database remains available the next time you run `docker compose up`.

### Run services separately

Start PostgreSQL and set `DATABASE_URL` to a PostgreSQL connection string. Then, from `backend/`, create a Python virtual environment, install `requirements.txt`, and start the API:

```sh
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

From `frontend/`, install the JavaScript packages and start Vite:

```sh
npm install
npm run dev
```

Vite proxies `/api` requests to `http://localhost:8000` by default. Set `VITE_API_TARGET` if the API runs at a different address.

## Demo accounts

All seeded accounts use the password `CampusBridge2026!`:

| Role | Email |
| --- | --- |
| Student | `student@campusbridge.edu` |
| Faculty | `faculty@campusbridge.edu` |
| Alumni | `alumni@campusbridge.edu` |
| Admin | `admin@campusbridge.edu` |
| System admin | `sysadmin@campusbridge.edu` |

The sign-in page also has one-click demo entry. Demo mode stores sample changes in browser local storage. Signing in against the API stores records in PostgreSQL.

## Implemented modules

- Email and password registration and sign-in, signed expiring sessions, role-aware navigation, and profile editing.
- Student, faculty, and alumni identity badges and profile views.
- Searchable faculty directory with department, expertise, campus, and availability filters.
- Academic feed with campus/category filtering, post creation, resource links, comments, likes, saves, and a saved-discussions view.
- Student consultation requests and faculty approval, decline, and reschedule actions.
- Faculty availability, weekly schedule blocks, and a student-facing profile preview.
- Faculty-only cross-department collaboration requests and responses.
- Admin account management, faculty verification, account activation controls, post moderation, and an admin-only shared profile cover setting.
- Role-specific sidebar navigation in a fixed-height, independently scrollable sidebar.

## Project structure

```text
frontend/                  React application and Vite configuration
backend/
  app/main.py              FastAPI routes and application startup
  app/database/            PostgreSQL connection, sessions, and SQLAlchemy models
docs/                       Requirement analysis and design-to-implementation mapping
```

## Prototype boundaries

The provided report does not specify an approved university email domain, identity provider credentials, or a mail service. Registration therefore accepts a valid email address without domain verification; Google and Microsoft buttons explain that OAuth setup is pending; password recovery and outbound notifications are not connected to email. The current schedule editor stores weekly time blocks without conflict detection or calendar integration. Admin reports, announcements, database backup/recovery, and system monitoring are described in the report but are not implemented in this prototype. API schema creation uses SQLAlchemy `create_all`; production schema changes should use versioned migrations and an institution-approved deployment setup.

The page examples, profile numbers, events, and seeded accounts are demonstration data, not live university records.
