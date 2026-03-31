# LMS Backend

Django REST Framework backend for an IIT/JEE preparation LMS with level-based course progression, exams, payments, and analytics.

## Tech Stack

- **Python 3.13** / **Django 5.2 LTS** / **Django REST Framework**
- **PostgreSQL** (production) / SQLite (development)
- **Redis** — Celery broker, cache, OTP storage
- **Celery** — async tasks (emails, analytics aggregation, exam auto-submit)
- **Razorpay** — payment gateway
- **Nginx** — reverse proxy, static file serving, rate limiting
- **Docker Compose** — containerized deployment
- **drf-spectacular** — OpenAPI schema generation
- **Prometheus** — metrics (`/metrics/`)
- **Sentry** — error tracking (production)
- **GitHub Actions** — CI pipeline (lint, security, tests, schema validation)

## Architecture

```
config/            Django project settings (base, development, production), URLs, WSGI/ASGI, Celery
core/              Shared utilities (permissions, pagination, constants, email, tasks, exceptions, throttling)
apps/
  users/           Auth, profiles, OTP, Google OAuth, password reset, preferences, issue reports
  levels/          Levels & weeks (content hierarchy)
  courses/         Courses, sessions, resources, bookmarks
  exams/           Exams, questions, attempts, proctoring, auto-submit
  payments/        Razorpay integration, purchases, transactions
  progress/        Session/level progress, dashboard, leaderboard, calendar
  doubts/          Doubt tickets & replies (student Q&A support)
  feedback/        Session feedback (ratings, difficulty, clarity)
  analytics/       Revenue & level analytics (admin)
  notifications/   User notifications
  home/            Banners, featured courses
  search/          Global search across levels, courses, sessions, questions
nginx/             Nginx reverse proxy configuration
docs/              API documentation
```

**Pattern:** Views -> Services -> Models. All business logic lives in service classes (`apps/*/services.py`). Views handle HTTP concerns only.

## Features

### Student Features
- **Authentication** — Email/password registration, login, Google OAuth, JWT tokens, OTP verification
- **Course Access** — Purchase-gated content with level-based progression
- **Video Progress** — Track watched seconds, auto-complete at 90% with feedback
- **Exams** — MCQ, multi-select MCQ, fill-in-the-blank with negative marking
- **Proctoring** — Full-screen exit, tab switch, voice, multi-face, extension detection
- **Dashboard** — Progress overview with next recommended action
- **Leaderboard** — Ranked by levels cleared and exam scores
- **Activity Calendar** — Daily sessions watched and exams taken
- **Doubt Tickets** — Q&A with admin replies and bonus marks
- **Bookmarks** — Save sessions for later
- **Notifications** — In-app notifications with preference controls
- **Search** — Global search across levels, courses, sessions, questions

### Admin Features
- **Full CRUD** — Levels, weeks, courses, sessions, resources, exams, questions, banners
- **Student Management** — View/update student profiles, filter by level
- **Doubt Management** — Reply, assign to faculty, update status, award bonus marks
- **Payment Management** — View purchases, extend validity
- **Analytics** — Daily revenue aggregation, level-wise pass rates
- **Exam Monitoring** — View attempts, filter by status/pass/disqualification

### Security
- JWT authentication with token blacklisting
- Rate limiting (Nginx + Django DRF scoped throttles)
- CORS configuration
- SSL/HSTS in production
- Secure cookies (HttpOnly, SameSite, Secure)
- Non-root Docker container
- Bandit security scanning in CI
- Dependency vulnerability auditing (pip-audit)

## Quick Start

```bash
# Clone and create virtualenv
git clone https://github.com/shathwik30/lms-backend.git
cd lms-backend
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

### With Docker (Production)

```bash
cp .env.example .env.docker
# Edit .env.docker:
#   DJANGO_ENV=production
#   DATABASE_URL=postgres://lms_user:lms_pass@db:5432/lms_db
#   CELERY_BROKER_URL=redis://redis:6379/0

docker compose up --build
```

This starts 6 containers: PostgreSQL, Redis, Django (Gunicorn, 3 workers), Celery worker, Celery beat, and Nginx.

### Development Docker (DB + Redis only)

```bash
docker compose -f docker-compose.dev.yml up -d
# Then run Django locally:
python manage.py runserver
```

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

## API Documentation

- **Swagger UI:** `http://localhost:8000/api/docs/`
- **ReDoc:** `http://localhost:8000/api/redoc/`
- **OpenAPI Schema:** `http://localhost:8000/api/schema/`
- **Detailed API Reference:** [`docs/API.md`](docs/API.md)

## API Endpoints Overview

| Module | Endpoints | Auth |
|---|---|---|
| **Auth** | Register, login, Google OAuth, logout, token refresh, password reset, OTP, change password | Public / Authenticated |
| **Profile** | Get/update profile, upload avatar, preferences, onboarding, issue reports | Authenticated |
| **Levels** | List levels, level details with weeks | Public |
| **Courses** | List by level, sessions (purchase-gated), session details, bookmarks | Student |
| **Exams** | View exam, start attempt, submit answers, view results, proctoring violations | Student |
| **Payments** | Initiate Razorpay order, verify payment, list purchases/transactions | Student |
| **Progress** | Dashboard, update watch progress, level/session progress, calendar, leaderboard | Student |
| **Doubts** | Create/list tickets, reply, admin assign/status/bonus | Student / Admin |
| **Feedback** | Submit session feedback (rating, difficulty, clarity) | Student |
| **Notifications** | List, mark read, mark all read, clear all, unread count | Authenticated |
| **Home** | Banners, featured courses | Public |
| **Search** | Global search (levels, courses, sessions, questions) | Authenticated |
| **Analytics** | Revenue analytics, level analytics | Admin |

## Environment Variables

See [`.env.example`](.env.example) for all available settings. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DJANGO_ENV` | `development` or `production` | `development` |
| `SECRET_KEY` | Django secret key | required |
| `DEBUG` | Enable debug mode | `False` |
| `DATABASE_URL` | Database connection string | `sqlite:///db.sqlite3` |
| `CELERY_BROKER_URL` | Redis URL for Celery | `redis://localhost:6379/0` |
| `CELERY_RESULT_BACKEND` | Redis URL for Celery results | `redis://localhost:6379/0` |
| `RAZORPAY_KEY_ID` | Razorpay API key | empty (skips gateway) |
| `RAZORPAY_KEY_SECRET` | Razorpay API secret | empty |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | empty |
| `FRONTEND_URL` | Frontend URL for password reset links | `http://localhost:3000` |
| `CORS_ALLOWED_ORIGINS` | Allowed CORS origins | empty |
| `SENTRY_DSN` | Sentry DSN (production only) | empty |
| `DEFAULT_FROM_EMAIL` | Email sender address | `noreply@lms.com` |

## CI/CD

GitHub Actions workflow (`.github/workflows/ci.yml`) runs on push/PR to `main` and `develop`:

1. **Lint** — ruff check + format verification
2. **Security** — bandit (high severity) + pip-audit (dependency vulnerabilities)
3. **Test** — full test suite with PostgreSQL + Redis, coverage >= 80%
4. **Schema** — OpenAPI schema validation via drf-spectacular

## Rate Limiting

Two layers of rate limiting:

**Nginx** (global): 10 requests/second with burst of 20

**Django DRF** (per-scope):

| Scope | Limit |
|---|---|
| Anonymous requests | 30/min |
| Authenticated requests | 120/min |
| Login/Register/OTP | 5/min |
| Payment operations | 10/min |
| Exam submission | 30/hr |
| Search | 60/min |
| Doubt creation | 10/min |
| Feedback | 20/min |
| Progress updates | 120/min |

## Monitoring

- **Health check:** `GET /api/v1/health/` — checks DB + Redis connectivity
- **Prometheus metrics:** `GET /metrics/` — request latency, DB queries, cache hits
- **Sentry:** Automatic error tracking in production (set `SENTRY_DSN`)

## Project Structure

```
lms-backend/
├── .github/workflows/ci.yml    # GitHub Actions CI pipeline
├── .pre-commit-config.yaml     # Ruff lint + format hooks
├── Dockerfile                  # Python 3.13-slim, Gunicorn, non-root user
├── docker-compose.yml          # Production: all 6 services
├── docker-compose.dev.yml      # Development: PostgreSQL + Redis only
├── nginx/default.conf          # Reverse proxy, gzip, security headers
├── requirements.txt            # Pinned dependencies
├── pyproject.toml              # Ruff, mypy, coverage config
├── manage.py
├── config/
│   ├── settings/
│   │   ├── base.py             # Shared settings
│   │   ├── development.py      # SQLite, console email, debug toolbar
│   │   └── production.py       # PostgreSQL, Redis cache, Sentry, HSTS
│   ├── celery.py               # Celery app with autodiscover
│   ├── urls.py                 # Root URL config
│   └── wsgi.py / asgi.py
├── core/
│   ├── constants.py            # Centralized enums, messages, thresholds
│   ├── emails.py               # EmailService class
│   ├── tasks.py                # Celery tasks (welcome, reset, purchase, exam, doubt emails)
│   ├── exceptions.py           # LevelLocked, SyllabusIncomplete, CourseExpired, PurchaseRequired
│   ├── permissions.py          # IsStudent, IsAdmin, IsStudentOwner
│   ├── pagination.py           # StandardPagination
│   ├── throttling.py           # SafeScopedRateThrottle
│   ├── models.py               # TimeStampedModel base
│   ├── views.py                # Health check
│   ├── services/
│   │   ├── eligibility.py      # Exam eligibility, next action logic
│   │   └── razorpay.py         # Razorpay API wrapper
│   └── test_utils.py           # TestFactory for test data
├── apps/
│   ├── users/                  # 6 models: User, StudentProfile, UserPreference, IssueReport + management commands
│   ├── levels/                 # 2 models: Level, Week
│   ├── courses/                # 4 models: Course, Session, Resource, Bookmark
│   ├── exams/                  # 6 models: Question, Option, Exam, ExamAttempt, AttemptQuestion, ProctoringViolation
│   ├── payments/               # 2 models: Purchase, PaymentTransaction
│   ├── progress/               # 2 models: SessionProgress, LevelProgress
│   ├── doubts/                 # 2 models: DoubtTicket, DoubtReply
│   ├── feedback/               # 1 model: SessionFeedback
│   ├── analytics/              # 2 models: RevenueAnalytics, LevelAnalytics
│   ├── notifications/          # 1 model: Notification
│   ├── home/                   # 1 model: Banner
│   └── search/                 # No models (searches across existing models)
└── docs/
    └── API.md                  # Detailed API reference with request/response examples
```

## License

This project is proprietary software. All rights reserved.
