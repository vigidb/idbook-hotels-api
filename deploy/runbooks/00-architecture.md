# 00 - Architecture

## Runtime Components

- Django API (Gunicorn)
- Django ASGI/WebSocket app (Daphne)
- Celery Beat (scheduler)
- Celery workers:
  - Transactional queue worker
  - Marketing campaign queue worker
- PostgreSQL
- Redis (broker)
- Nginx (reverse proxy, TLS termination)

## Queue topology

- Dev:
  - `dev-email-send-queue`
  - `dev-marketing-campaign-queue`
- Prod:
  - `email-send-queue`
  - `marketing-campaign-queue`

Other queues already in project:
- `airiq-token-queue`
- `recpay-initiate-queue`

## Data flow (campaign)

1. Campaign scheduled/send-now.
2. `enqueue_campaign_contacts_task` builds campaign contacts.
3. Due contacts get queued to `send_campaign_batch_task`.
4. `process_due_campaign_contacts_task` periodically drains delayed steps.
5. Message outcomes written to `MessageLog`.

## High-level scaling rules

- Split transactional and marketing workers.
- Keep Beat as a single instance.
- Move DB and Redis off app host early.
