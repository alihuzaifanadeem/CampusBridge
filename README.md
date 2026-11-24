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

Docker Compose runs PostgreSQL 16 in the `database` service. FastAPI connects to it at `database:5432` on Compose's private network. The database is also available to desktop tools on `127.0.0.1:5433`; this alternate port avoids colliding with a locally installed PostgreSQL server on port 5432. The database files are kept in the named Docker volume `campusbridge-data`, not in a source-code folder. The PostgreSQL engine and session are configured in `backend/app/database/connection.py`, and ORM models are in `backend/app/database/models.py`. The API creates the tables at startup. To inspect the database from a terminal, run:

```sh
docker compose exec database psql -U campusbridge -d campusbridge
```

`docker compose down` stops the containers and preserves the database and uploaded-cover images. They remain available the next time you run `docker compose up`.

To use the pgAdmin 4 desktop app, first start the Compose services, then register a server in pgAdmin (**Object → Register → Server**). Set the server name to `CampusBridge Docker`; on the **Connection** tab use host `127.0.0.1`, port `5433`, maintenance database `campusbridge`, username `campusbridge`, and password `campusbridge_dev`. Expand **Servers → CampusBridge Docker → Databases → campusbridge → Schemas → public → Tables**. To view table contents, right-click a table and choose **View/Edit Data → All Rows**.

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
- Account signup requests are held for admin review before a user account is created; student requests require a university student ID and front/back card images that admins can inspect before approval. Card images are stored privately in PostgreSQL while pending and deleted after approval or rejection.
- Searchable faculty directory with department, expertise, campus, and availability filters.
- Academic feed with campus/category filtering, post creation, resource links, comments, likes, saves, and a saved-discussions view.
- Refresh the home feed without reloading the application with the feed refresh button or by double-clicking **Home feed**.
- Student consultation requests and faculty approval, decline, and reschedule actions.
- Faculty availability, weekly schedule blocks, and a student-facing profile preview.
- Faculty-only cross-department collaboration requests and responses.
- Admin account management, signup approval/rejection, faculty verification, account activation controls, post moderation, and an admin-only shared profile cover setting.
- Admins can upload a PNG, JPG, or WebP shared profile cover (up to 2 MB) and set its display width (320–2400 px) and height (100–500 px); image files persist in `campusbridge-media` and cover settings in PostgreSQL.
- Each signed-in user can upload or remove their own PNG, JPG, or WebP profile photo (up to 10 MB); photos appear on avatars throughout the app and persist in `campusbridge-media`.
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
