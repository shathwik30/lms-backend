# LMS Backend

Django REST Framework backend for an IIT/JEE preparation LMS with level-based course progression, exams, payments, and analytics.

## Tech Stack

- **Python 3.13** / **Django 6.0** / **Django REST Framework**
- **PostgreSQL** (production) / SQLite (development)
- **Redis** — Celery broker, cache, OTP storage
- **Celery** — async tasks (emails, analytics aggregation, exam auto-submit)
- **Razorpay** — payment gateway
- **drf-spectacular** — OpenAPI schema generation
- **Prometheus** — metrics (`/metrics/`)
- **Sentry** — error tracking (production)

## Architecture

```
config/            Django project settings, URLs, WSGI/ASGI
core/              Shared utilities (permissions, pagination, constants, email, tasks)
apps/
  users/           Auth, profiles, OTP, Google OAuth, password reset
  levels/          Levels & weeks (content hierarchy)
  courses/         Courses, sessions, resources, bookmarks
  exams/           Exams, questions, attempts, proctoring
  payments/        Razorpay integration, purchases, transactions
  progress/        Session/level progress, dashboard, leaderboard, calendar
  doubts/          Doubt tickets & replies
  feedback/        Session feedback
  analytics/       Revenue & level analytics (admin)
  notifications/   User notifications
  certificates/    Level completion certificates
  home/            Banners, featured courses
  search/          Global search
```

**Pattern:** Views -> Services -> Models. All business logic lives in service classes (`apps/*/services.py`). Views handle HTTP concerns only.

## Quick Start

```bash
# Clone and create virtualenv
python -m venv venv && source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Run migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Start development server
python manage.py runserver
```

### With Docker

```bash
cp .env.example .env.docker
# Edit .env.docker (set DATABASE_URL=postgres://lms_user:lms_pass@db:5432/lms_db)

docker compose up --build
```

This starts: PostgreSQL, Redis, Django (gunicorn), Celery worker, Celery beat, and Nginx.

## Development

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
```

Runs **ruff** lint + format on every commit automatically.

### Running Tests

```bash
# All tests
python manage.py test

# Specific app
python manage.py test apps.exams

# With coverage
coverage run --source=apps,core manage.py test
coverage report
```

523 tests, 9 skipped (PostgreSQL-only features on SQLite).

### Linting & Formatting

```bash
ruff check apps/ core/ config/        # lint
ruff check --fix apps/ core/ config/  # auto-fix
ruff format apps/ core/ config/       # format
```

### Type Checking

```bash
mypy apps/ core/
```

### API Documentation

- Swagger UI: `http://localhost:8000/api/docs/`
- ReDoc: `http://localhost:8000/api/redoc/`
- OpenAPI Schema: `http://localhost:8000/api/schema/`

## Environment Variables

See [`.env.example`](.env.example) for all available settings. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_ENV` | `development` or `production` | `development` |
| `SECRET_KEY` | Django secret key | required |
| `DATABASE_URL` | Database connection string | `sqlite:///db.sqlite3` |
| `CELERY_BROKER_URL` | Redis URL for Celery | `redis://localhost:6379/0` |
| `RAZORPAY_KEY_ID` | Razorpay API key | empty (skips gateway) |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | empty |
| `SENTRY_DSN` | Sentry DSN (production only) | empty |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins | empty |

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

1. **Lint** — ruff check + format
2. **Security** — bandit + pip-audit
3. **Test** — full test suite with PostgreSQL + Redis, coverage report
4. **Schema** — OpenAPI schema validation

## Monitoring

- **Prometheus metrics**: `GET /metrics/` (request latency, DB queries, etc.)
- **Health check**: `GET /api/v1/health/` (DB + Redis connectivity)
- **Sentry**: Automatic error tracking in production (set `SENTRY_DSN`)
