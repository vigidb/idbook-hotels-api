# 02 - Environment Variables

Store real env files outside git:

- Dev/Test: `/etc/idbook/dev-api.env`
- Prod: `/etc/idbook/prod-api.env`

Seed from templates:

- `deploy/systemd/env/dev/idbook-api.env.example`
- `deploy/systemd/env/prod/idbook-api.env.example`

## Minimum required variables

- Django core: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `ENVIRONMENT`
- Database: `DATABASE_NAME`, `DATABASE_USER`, `DATABASE_PASSWORD`, `DATABASE_HOST`, `DATABASE_PORT`
- Redis broker: `CELERY_BROKER_URL`
- Email providers and keys used by your app
- Any third-party keys (ImageKit, payment gateways, SMS providers)

## Safety rules

- Never commit real env files.
- Keep dev and prod Redis/DB isolated.
- Keep `ENVIRONMENT=dev` only on dev/test server.
