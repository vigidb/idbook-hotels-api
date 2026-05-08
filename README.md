# IDBOOK Hotels API

Django REST Framework backend for the IDBOOK hotel booking platform (web, Android, iOS): listings, bookings, payments, customers, partners, and related services.

For architecture, env vars, and day-to-day patterns, see [CLAUDE.md](CLAUDE.md).

## Requirements

- Python 3.11
- PostgreSQL
- Optional: Redis (Celery), Docker (see `IDBOOKAPI/docker-compose.yml`)

## Setup

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
cd IDBOOKAPI
pip install -r requirements.txt
```

Configure environment (see `IDBOOKAPI/IDBOOKAPI/.env` and CLAUDE.md), then:

```bash
python manage.py migrate
python manage.py createsuperuser   # optional
```

## Run the app

```bash
cd IDBOOKAPI
python manage.py runserver
```

API docs (when enabled): ReDoc at `/api/v1/docs/`, Swagger at `/api/v1/docs/swagger/`.

**Docker:** from `IDBOOKAPI`, `docker-compose up` (includes PostgreSQL and the web service).

## Celery

Run workers from the `IDBOOKAPI` directory after activating the venv. Queue names and routes are defined in `IDBOOKAPI/IDBOOKAPI/celery.py`.

### Queues used by this project

| Queue | Used when `ENVIRONMENT` is `dev`, `development`, `local`, or `test` | Production (`ENVIRONMENT` otherwise, e.g. `production`) |
|-------|----------------------------------------------------------------------|---------------------------------------------------------|
| Transactional email/SMS (OTP, booking, hotel, org, flight notifications) | `dev-email-send-queue` | `email-send-queue` |
| Marketing / messaging campaigns (`apps.messaging.tasks.*`) | `dev-marketing-campaign-queue` | `marketing-campaign-queue` |
| **Default / unrouted tasks** (anything without an explicit route in `celery.py`) | `dev-general-queue` | `general-queue` |
| AirIQ token tasks | `dev-airiq-token-queue` | `airiq-token-queue` |
| Recurring payment + wallet expiry (`initiate_recurring_payment`, `wallet_expiry_task`) | `dev-recpay-initiate-queue` | `recpay-initiate-queue` |

Override the default unrouted queue name with **`CELERY_TASK_DEFAULT_QUEUE`** in `.env` if needed.

### One worker — development

Use with **`ENVIRONMENT=dev`** (or `local` / `test`) so tasks are published to the `dev-*` queues. Consume **all** queues below (includes the general catch-all):

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI worker -l info -Q dev-email-send-queue,dev-marketing-campaign-queue,dev-general-queue,dev-airiq-token-queue,dev-recpay-initiate-queue
```

### One worker — production

Use with **production** settings. Consume **all** queues:

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI worker -l info -Q email-send-queue,marketing-campaign-queue,general-queue,airiq-token-queue,recpay-initiate-queue
```

**Production tip:** To keep bulk campaigns from competing with OTP on the same process, run **two** workers instead — e.g. one with `-Q email-send-queue,airiq-token-queue,recpay-initiate-queue,general-queue` and one with `-Q marketing-campaign-queue` — as described in [docs/Messaging_Scalability_Reliability_Production_Guide.md](docs/Messaging_Scalability_Reliability_Production_Guide.md).

### Celery Beat

Beat must run separately unless you embed it on a worker (see below).  
This project uses `django-celery-beat` as the scheduler backend, so periodic tasks are managed in Django admin.

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI beat -l info
```

**Scheduler source of truth**

- Default/recommended: admin-managed periodic tasks (`django_celery_beat`).
- Optional fallback: code-defined Beat schedule by setting `CELERY_USE_CODE_BEAT_SCHEDULE=true`.
- Do not run both approaches for the same periodic tasks.

**Optional:** embed Beat on the dev worker (same `-Q` as the dev one-liner above):

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI worker -l info -Q dev-email-send-queue,dev-marketing-campaign-queue,dev-general-queue,dev-airiq-token-queue,dev-recpay-initiate-queue -B -s celerybeat-schedule
```

**Optional:** embed Beat on the production all-queues worker:

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI worker -l info -Q email-send-queue,marketing-campaign-queue,general-queue,airiq-token-queue,recpay-initiate-queue -B -s celerybeat-schedule
```

**Messaging campaigns:** `enqueue_campaign_contacts_task` only queues sends for contacts that are already due. Future-dated steps need **`process_due_campaign_contacts_task`** (configured as periodic task), which runs on the marketing campaign queue. Without a worker on that queue (and Beat), campaign work stalls in the broker.

### Production worker split (recommended)

Use dedicated workers to isolate periodic/marketing load from transactional traffic:

```bash
# Transactional workload (OTP, booking, email, notifications, misc unrouted tasks)
celery -A IDBOOKAPI worker -l info -Q email-send-queue,airiq-token-queue,recpay-initiate-queue,general-queue --concurrency=4

# Marketing workload
celery -A IDBOOKAPI worker -l info -Q marketing-campaign-queue --concurrency=2

# Recurring/wallet periodic workload
celery -A IDBOOKAPI worker -l info -Q recpay-initiate-queue --concurrency=1
```

For **limits, providers, and operational detail**, see [docs/Messaging_Scalability_Reliability_Production_Guide.md](docs/Messaging_Scalability_Reliability_Production_Guide.md).

### Redis URL examples (broker, cache, Channels)

Broker, HTTP cache, and WebSockets should use **different Redis DB indexes** (`/0`, `/1`, …) or separate instances so workloads do not flush each other’s keys.

| Purpose | Env var | Dev example | Production-style example |
|---------|---------|-------------|---------------------------|
| Celery broker | `CELERY_BROKER_URL` | `redis://127.0.0.1:6379/0` | `rediss://:PASSWORD@redis.internal:6380/0` |
| Django HTTP cache (optional) | `REDIS_CACHE_URL` | `redis://127.0.0.1:6379/2` | `rediss://:PASSWORD@redis.internal:6380/2` |
| WebSocket channel layer | `REDIS_CHANNEL_LAYER_URL` | `redis://127.0.0.1:6379/3` | `rediss://:PASSWORD@redis.internal:6380/3` |

- **`redis://`** — cleartext (common on localhost or private VPC).
- **`rediss://`** — TLS (typical for managed Redis).
- Password-only auth URL shape: `redis://:PASSWORD@HOST:6379/0`.

If **`REDIS_CACHE_URL`** is empty, Django uses **`LocMemCache`** (per process only). Optional tuning when Redis cache is enabled: **`CACHE_KEY_PREFIX`**, **`CACHE_DEFAULT_TIMEOUT`** (seconds).

### Task results (`django-db`) and Beat schedules

- **`CELERY_RESULT_BACKEND = django-db`** writes Celery **task result** rows via **`django_celery_results`** into PostgreSQL using your **`DATABASES`** setting (usually alias **`default`**). Nothing automatically creates a *new* database server—you point Django at an existing Postgres; **`migrate`** creates the tables.
- To use a **different Postgres** for results only, add another **`DATABASES`** entry and a **`DATABASE_ROUTER`** that directs `django_celery_results` models to that alias.
- **`django-celery-beat`** periodic tasks are the same idea: they are Django models stored in your configured database(s), edited in admin. The **broker** for executing tasks remains Redis (**`CELERY_BROKER_URL`**).

## Optional dev workflows

**SSH tunnel (AirIQ proxy):**

```bash
ssh -L 8888:localhost:8888 ubuntu@13.50.52.0 -i idbook-key.pem
```

**PostgreSQL backup / restore:**

```bash
pg_dump -h localhost -U <db_username> -Fc <database_name> > db_backup.dump
# pg_restore -d <database_name> db_backup.dump
```

**Import airline reference data:**

```bash
cd IDBOOKAPI
python manage.py import_openflights_airlines --truncate
```

**Payment gateway testing via ngrok**

```bash
python manage.py runserver 0.0.0.0:8000
```
```bash
ngrok http 8000
```

**WebSockets (ASGI):**

```bash
daphne -b 0.0.0.0 -p 8000 IDBOOKAPI.asgi:application
```

**Razorpay (example endpoint):** `http://127.0.0.1:8000/api/v1/booking/razorpay-payment/`

- [Razorpay test cards](https://razorpay.com/docs/payments/payments/test-card-details/#to-use-the-test-card-details)
- [Razorpay test UPI](https://razorpay.com/docs/payments/payments/test-upi-details/)

## Tests

```bash
cd IDBOOKAPI
pytest
```
