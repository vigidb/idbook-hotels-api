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

| Queue | Used when `ENVIRONMENT=dev` | Used in production (`ENVIRONMENT` not `dev`) |
|-------|----------------------------|-----------------------------------------------|
| Transactional email/SMS (OTP, booking, hotel, org, flight notifications) | `dev-email-send-queue` | `email-send-queue` |
| Marketing / messaging campaigns (`apps.messaging.tasks.*`) | `dev-marketing-campaign-queue` | `marketing-campaign-queue` |
| AirIQ token tasks (always) | `airiq-token-queue` | `airiq-token-queue` |
| Recurring payment + wallet expiry Beat jobs (always) | `recpay-initiate-queue` | `recpay-initiate-queue` |

### One worker — development

Use with **`ENVIRONMENT=dev`** so tasks are published to the `dev-*` queues. This single process consumes **all** queues referenced for dev plus the two environment-agnostic queues:

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI worker -l info -Q dev-email-send-queue,dev-marketing-campaign-queue,airiq-token-queue,recpay-initiate-queue
```

### One worker — production

Use with **production** settings (`ENVIRONMENT` anything other than `dev`). This consumes **all** queues referenced in `celery.py` for that mode:

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI worker -l info -Q email-send-queue,marketing-campaign-queue,airiq-token-queue,recpay-initiate-queue
```

**Production tip:** To keep bulk campaigns from competing with OTP on the same process, run **two** workers instead — e.g. one with `-Q email-send-queue,airiq-token-queue,recpay-initiate-queue` and one with `-Q marketing-campaign-queue` — as described in [docs/Messaging_Scalability_Reliability_Production_Guide.md](docs/Messaging_Scalability_Reliability_Production_Guide.md).

### Celery Beat

Beat must run separately unless you embed it on a worker (see below). It schedules tasks onto the same queues as in the table (e.g. `process_due_campaign_contacts_task` → marketing campaign queue).

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI beat -l info
```

**Optional:** embed Beat on the dev worker (same `-Q` as the dev one-liner above):

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI worker -l info -Q dev-email-send-queue,dev-marketing-campaign-queue,airiq-token-queue,recpay-initiate-queue -B -s celerybeat-schedule
```

**Optional:** embed Beat on the production all-queues worker:

```bash
cd IDBOOKAPI
celery -A IDBOOKAPI worker -l info -Q email-send-queue,marketing-campaign-queue,airiq-token-queue,recpay-initiate-queue -B -s celerybeat-schedule
```

**Messaging campaigns:** `enqueue_campaign_contacts_task` only queues sends for contacts that are already due. Future-dated steps need **`process_due_campaign_contacts_task`**, which Beat runs every minute on the marketing campaign queue for your environment. Without a worker on that queue (and Beat), campaign work stalls in the broker.

For **limits, providers, and operational detail**, see [docs/Messaging_Scalability_Reliability_Production_Guide.md](docs/Messaging_Scalability_Reliability_Production_Guide.md).

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
