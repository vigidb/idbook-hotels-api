# 01 - Prerequisites

## OS packages (Ubuntu example)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx redis-server postgresql postgresql-contrib
```

## Application user and directories

```bash
sudo useradd -m -s /bin/bash idbook || true
sudo mkdir -p /opt/idbook /var/log/idbook /etc/idbook
sudo chown -R idbook:idbook /opt/idbook /var/log/idbook
```

## Code checkout

```bash
sudo -u idbook git clone <repo-url> /opt/idbook/idbook-hotels-api
```

## Virtual environment

```bash
sudo -u idbook bash -lc 'cd /opt/idbook/idbook-hotels-api/IDBOOKAPI && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt'
```

## Verify Python app boots

```bash
sudo -u idbook bash -lc 'cd /opt/idbook/idbook-hotels-api/IDBOOKAPI && source venv/bin/activate && python manage.py check'
```
