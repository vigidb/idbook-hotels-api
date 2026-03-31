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

Run workers from the `IDBOOKAPI` directory after activating the venv.

**Production-style email worker:**

```bash
celery -A IDBOOKAPI worker -l info -Q email-send-queue
```

**Local dev** (queues used when `ENVIRONMENT=dev` plus flight/recurring queues):

```bash
celery -A IDBOOKAPI worker -l info -Q dev-email-send-queue,email-send-queue,airiq-token-queue,recpay-initiate-queue
```

**Beat** (scheduled tasks, e.g. recurring payments — worker consumes `recpay-initiate-queue` with embedded beat):

```bash
celery -A IDBOOKAPI worker -l info -Q recpay-initiate-queue -B -s recpay-task.schedule
```

Beat schedule lives in `IDBOOKAPI/IDBOOKAPI/celery.py`.

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
