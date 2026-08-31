# 07 - Observability and Troubleshooting

## What to monitor

- API latency and error rate
- DB CPU/locks/slow queries
- Redis memory and connection count
- Celery queue lag (oldest task age)
- Campaign counters: pending, queued, sent, failed

## Common checks

```bash
sudo systemctl status idbook-django idbook-daphne idbook-celery-worker-tx idbook-celery-worker-marketing idbook-celery-beat
sudo journalctl -u idbook-celery-worker-marketing -n 200 --no-pager
```

## Campaign delayed-step stuck checklist

1. Confirm campaign status is `scheduled` or `running`.
2. Check pending contacts with `scheduled_at <= now`.
3. Confirm Beat is alive.
4. Confirm marketing worker consumes marketing queue.
5. Confirm no queue mismatch (`dev-*` vs prod queues).
