# 03 - PostgreSQL Setup

## Create DB and user

```bash
sudo -u postgres psql <<'SQL'
CREATE USER idbook_user WITH PASSWORD 'replace_me';
CREATE DATABASE idbook_db OWNER idbook_user;
GRANT ALL PRIVILEGES ON DATABASE idbook_db TO idbook_user;
SQL
```

## Migrations

```bash
sudo -u idbook bash -lc 'cd /opt/idbook/idbook-hotels-api/IDBOOKAPI && source venv/bin/activate && python manage.py migrate'
```

## Backups

- Use `deploy/postgres/backup.sh.example` as baseline.
- Schedule daily backups and verify restore monthly.

## Health checks

```bash
sudo -u postgres psql -c "\l"
sudo -u postgres psql -d idbook_db -c "SELECT now();"
```
