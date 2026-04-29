# 06 - Celery Workers and Beat

## Principles

- Run only one Beat per environment.
- Split transactional and marketing workers.
- Ensure queue names match `ENVIRONMENT`.

## Production worker commands

Transactional worker:

```bash
celery -A IDBOOKAPI worker -l info -Q email-send-queue,airiq-token-queue,recpay-initiate-queue --hostname=tx@%h
```

Marketing worker:

```bash
celery -A IDBOOKAPI worker -l info -Q marketing-campaign-queue --hostname=mkt@%h
```

Beat:

```bash
celery -A IDBOOKAPI beat -l info
```

## Verify campaign flow

- Step 1 sends immediately for due contacts.
- Delayed steps drain via `process_due_campaign_contacts_task`.
- No queue backlog growth under normal load.
