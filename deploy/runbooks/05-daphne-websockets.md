# 05 - Daphne + WebSockets

Run ASGI separately from Gunicorn.

## Manual test

```bash
sudo -u idbook bash -lc 'cd /opt/idbook/idbook-hotels-api/IDBOOKAPI && source venv/bin/activate && daphne -b 127.0.0.1 -p 8001 IDBOOKAPI.asgi:application'
```

## Nginx routing

Route WebSocket paths to Daphne upstream, and standard HTTP API to Gunicorn.

## Verify

- WebSocket handshake succeeds.
- No mixed proxy timeout errors.
