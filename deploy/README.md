# Deployment Guide Index

This folder contains production-oriented deployment documentation and templates
for the IDBOOK Hotels API stack.

## Structure

- `runbooks/`: step-by-step operational guides.
- `systemd/common/`: reusable unit files for app and workers.
- `systemd/env/`: environment variable templates (no secrets).
- `nginx/`: Nginx site configs (dev/prod examples).
- `gunicorn/`: Gunicorn runtime config template.
- `scripts/`: helper scripts for deploy and health checks.
- `postgres/`: backup/restore helper templates.

## Environments

Use separate environment files and process instances for dev/test vs production.

- Dev/Test: `ENVIRONMENT=dev` (uses `dev-*` queues)
- Prod: `ENVIRONMENT=production` (uses production queue names)

## First-time setup checklist

1. Copy env template and fill values on server:
   - `/etc/idbook/dev-api.env` or `/etc/idbook/prod-api.env`
2. Copy systemd units into `/etc/systemd/system/`.
3. Install Python dependencies.
4. Run database migrations.
5. Enable and start services:
   - Django (Gunicorn)
   - Daphne (WebSockets)
   - Celery worker (transactional queues)
   - Celery worker (marketing queue)
   - Celery beat (single instance only)
6. Configure Nginx and TLS.
7. Verify health and smoke test messaging campaign flow.

## Commands

Reload systemd after unit changes:

```bash
sudo systemctl daemon-reload
```

Enable on boot:

```bash
sudo systemctl enable idbook-django idbook-daphne idbook-celery-worker-tx idbook-celery-worker-marketing idbook-celery-beat
```

Restart all services:

```bash
sudo systemctl restart idbook-django idbook-daphne idbook-celery-worker-tx idbook-celery-worker-marketing idbook-celery-beat
```

## Important notes

- Do not commit real secrets.
- Run only one Beat per environment.
- Keep broker and DB isolated between dev/test and production.
