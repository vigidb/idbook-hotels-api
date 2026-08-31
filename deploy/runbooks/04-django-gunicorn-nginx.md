# 04 - Django + Gunicorn + Nginx

## Gunicorn

Use `deploy/gunicorn/gunicorn.conf.py.example` as baseline.

Manual test:

```bash
sudo -u idbook bash -lc 'cd /opt/idbook/idbook-hotels-api/IDBOOKAPI && source venv/bin/activate && gunicorn IDBOOKAPI.wsgi:application -c ../deploy/gunicorn/gunicorn.conf.py.example'
```

## Nginx

Copy either:

- `deploy/nginx/dev.conf.example`
- `deploy/nginx/prod.conf.example`

into `/etc/nginx/sites-available/idbook.conf`, then symlink to `sites-enabled`.

Validate and reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## Verify

- `GET /` and API endpoints respond via Nginx.
- Static files and admin assets load.
