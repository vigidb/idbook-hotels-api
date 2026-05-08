# Messaging scalability, reliability, and production setup

This document describes **how campaign email and SMS are executed** in Idbook’s API, **dev vs production** differences, **limits encoded in software**, **on-time delivery and duplicate behavior**, and **operational risks**—especially **sharing infrastructure with transactional and authentication** traffic.

**Primary stack (as configured in product/engineering):**

| Channel | Delivery path | Regulatory / vendor context |
|---------|----------------|----------------------------|
| **Email** | SMTP (commonly **Gmail** / Google Workspace accounts via Django email settings) | Sending limits, reputation, and authentication (SPF/DKIM/DMARC) are enforced by Google and your domain setup—not by this app. |
| **SMS** | **Fast2SMS** template API (`send_template_sms` in `apps/sms_gateway/mixins/fastwosms_mixins.py`) | Indian **DLT** (e.g. **Jio** and other operator DLT platforms) requires registered templates, headers, and variable patterns; Fast2SMS is the integration layer toward those registered templates. |

This guide is **not** a substitute for Google’s or Fast2SMS’s current rate cards, quotas, or DLT portal rules—verify those with your accounts.

---

## 1. Dev vs production (Celery queues)

Routing is defined in `IDBOOKAPI/IDBOOKAPI/celery.py`:

| Environment (`ENVIRONMENT`) | Transactional email/SMS queue | Marketing / campaign queue | Default (unrouted tasks) |
|-----------------------------|------------------------------|----------------------------|----------------------------|
| **`dev`** (and `local` / `test`) | `dev-email-send-queue` | `dev-marketing-campaign-queue` | `dev-general-queue` |
| **Non-dev (e.g. production)** | `email-send-queue` | `marketing-campaign-queue` | `general-queue` |

**Transactional queue** (OTP, booking/hotel email & SMS, org SMS, flight notifications, etc.) — time-sensitive paths stay here.

**Marketing campaign queue** — bulk campaign work only:

- `apps.messaging.tasks.enqueue_campaign_contacts_task`
- `apps.messaging.tasks.send_campaign_batch_task`
- `apps.messaging.tasks.process_due_campaign_contacts_task` (also scheduled by **Celery Beat** every minute; Beat enqueues to the marketing queue)

**Implication:** Run **at least one worker** on each queue in production so campaigns do not block OTP and confirmations. A single worker that listens to **both** queues still shares one process’s throughput; for hard isolation, use **separate worker pools** (or machines) per queue.

---

## 2. Software limits (scalability constraints)

These are **implemented in code** today (`apps/messaging/tasks.py` unless noted).

| Constraint | Value | Purpose |
|------------|--------|---------|
| **Batch size** | **100** `CampaignContact` IDs per `send_campaign_batch_task` | Bounds memory and time per Celery task; comment notes rate limiting **can be added later** (not present now). |
| **Initial enqueue cap** | **10,000** due `CampaignContact` rows per `enqueue_campaign_contacts_task` run | Avoids exploding the broker with one campaign; additional pending rows rely on the periodic task. |
| **Periodic drain** | Up to **1,000** pending-due IDs per minute via `process_due_campaign_contacts_task` | Picks globally pending rows (all campaigns), chunks into batches of 100. |
| **Beat interval** | **Every 1 minute** | Delayed or future `scheduled_at` steps become eligible for batch enqueue on this cadence—not sub-minute precision. |
| **Sends inside one batch** | **Sequential** (loop over contacts) | Throughput per worker process is roughly “messages ÷ (average SMTP/API latency)” for that batch—no intra-batch parallelism. |
| **Contact pipeline rows** | `bulk_create(..., ignore_conflicts=True)` on `CampaignContact` | Relies on DB uniqueness; see [Section 5](#5-duplicates-on-time-delivery-and-idempotency). |

There is **no application-level** per-second throttle for campaigns, SMTP, or Fast2SMS in this layer—**provider and worker concurrency** dominate.

---

## 3. Provider-specific constraints

### 3.1 Email (Gmail / Google)

Typical concerns when using **Gmail SMTP** for **bulk or mixed** (transactional + marketing) sending:

- **Daily sending limits** depend on account type (consumer Gmail vs Google Workspace) and Google’s policies; **high-volume marketing** often exceeds comfortable SMTP limits.
- **Reputation:** Shared IP/domain reputation; sudden large campaigns can affect **all** mail from that identity (including OTP and booking mail if the same SMTP user is used).
- **Deliverability:** SPF, DKIM, DMARC, and list hygiene matter; Gmail may throttle or defer.
- **Operational:** App passwords / OAuth, “less secure app” restrictions, and Workspace admin policies can block or cap sends.

**Recommendation for production at meaningful volume:** Use a **transactional ESP** or **SMTP relay** with explicit marketing/transactional separation, or **separate SMTP identities** for campaigns vs OTP/booking—**even if** the code path remains Django `send_mail` / `send_email_with_smtp_config`.

### 3.2 SMS (Fast2SMS + DLT / Jio)

- **DLT compliance:** Template IDs, entity IDs, variable ordering, and content must match what is registered on the operator/DLT side; mismatches produce **hard failures** (visible in `MessageLog.provider_response` and campaign contact `error_message`).
- **Throughput:** Fast2SMS and operator policies define QPS and daily caps; the app does not enforce them.
- **Shared integration:** `send_template_sms` is used by **booking and other modules** as well as campaigns—**one API key / account** shares quota and error budget with everything else.

---

## 4. On-time delivery

**What “on time” means in the current design:**

1. **`scheduled_at`** on each `CampaignContact` is computed from `campaign.schedule_time` (or “now”) plus step delays (`build_campaign_contacts_for_step` in `apps/messaging/services.py`).
2. When a campaign is scheduled or sent, **`enqueue_campaign_contacts_task`** queues batches only for contacts that are **already due** (`scheduled_at <= now` or null), up to **10,000** IDs.
3. Contacts due **later** (multi-step delays) remain **`PENDING`** until **`process_due_campaign_contacts_task`** runs (by default **once per minute**) and enqueues batches (up to **1,000** IDs per run across the whole system).

**Precision:** Delivery is **minute-granularity at best** for anything relying on Beat, not second-level. Within a batch, order is **worker-dependent** and **sequential** per task.

**Backlog:** Large audiences can wait in the Celery queue behind other tasks; “on time” assumes **enough workers** and **provider capacity**.

---

## 5. Duplicates, on-time delivery, and idempotency

### 5.1 Duplicate protection (same campaign)

`CampaignContact` enforces **`unique_together = ("campaign", "step", "contact")`** (`apps/messaging/models.py`).  
`bulk_create(..., ignore_conflicts=True)` skips inserting a second row for the same triple.

So **the same contact should not get two pipeline rows for the same step** of the same campaign from a normal `build_campaign_contacts` run.

### 5.2 When duplicates or double sends can still happen

- **Operational:** Calling **schedule / send again** after partial progress may create **new** rows for steps that did not exist before or after **reset** + rebuild; always treat “send now” as a **business event**, not a harmless refresh.
- **Retries:** Celery **automatic retries are not configured** on `send_campaign_batch_task` in code; manual requeue or a future retry feature could change behavior—design any retry to be **idempotent** at the provider where possible.
- **Provider behavior:** Rare edge cases (timeouts after accept) are possible; `MessageLog` is the audit trail.

### 5.3 Same person, multiple campaigns

Uniqueness is **per campaign**, not global. A contact can receive **multiple** messages from **different** campaigns or steps.

---

## 6. Reliability (what the app guarantees today)

**Strengths**

- **Asynchronous processing** via Celery; API calls return after enqueueing work (see `Messaging_Campaigns_Operations_Guide.md`).
- **Per-recipient state:** `CampaignContact` status (`PENDING`, `SENT`, `FAILED`, opt-out, blacklisted, etc.).
- **Audit:** `MessageLog` rows with channel, status, provider label, and `provider_response` JSON.

**Gaps (important for SLAs)**

- **No built-in Celery `autoretry` / backoff** on campaign batch sends in `apps/messaging/tasks.py`.
- **No in-app rate limiter** for Gmail or Fast2SMS (comment acknowledges this).
- **Failures** are recorded; **automatic reconciliation** (e.g. retry failed only) is not part of the default campaign task flow.

---

## 7. Volume tiers: what to expect and what to do

Use this as a **planning matrix**; tune with real latency measurements.

| Tier | Approx. scale (indicative) | Typical bottlenecks | Suggested setup |
|------|----------------------------|---------------------|-----------------|
| **Low** | Up to a few hundred recipients per campaign | Occasional queue delay | Workers on **`email-send-queue`** and **`marketing-campaign-queue`** (can be one process with `-Q` listing both); Beat enabled; separate **SMTP identity** for marketing if mixed with OTP. |
| **Medium** | ~1k–10k per campaign | 10k initial enqueue cap; sequential sends in batches; Gmail daily limits if one account | **Multiple Celery workers** or higher concurrency; monitor `MessageLog` failure rate; consider **Workspace** or relay; **dedicated Fast2SMS** key or sub-account for marketing if policy allows. |
| **High** | 10k–100k+ | Beat drain (1k/min global), broker depth, Gmail/Fast2SMS caps | **Dedicated workers** on `marketing-campaign-queue` (routing is already separate from transactional); **ESP** for email; **approved high-throughput** SMS route; stagger campaigns. |
| **Very high** | Marketing-scale broadcast | All of the above + compliance and bounce handling | Specialist bulk messaging architecture (segmentation workers, bounce webhooks, suppression lists, warm-up plans)—beyond current campaign module assumptions. |

**Rule of thumb:** If transactional latency (OTP, booking confirmation) spikes when campaigns run, you are **queue- or provider-limited**—scale workers or **isolate** campaign traffic.

---

## 8. Production setup checklist

1. **Celery worker(s)** consuming **`email-send-queue`** (production) or **`dev-email-send-queue`** (dev) for transactional email/SMS, with enough **concurrency** for OTP and booking peaks.
2. **Celery worker(s)** consuming **`marketing-campaign-queue`** (or **`dev-marketing-campaign-queue`**) for `apps.messaging.tasks.*`, with concurrency sized for campaign batch volume `(tasks in flight) × (batch size 100) × (send latency)`.
3. **Celery Beat** running with schedule from `celery.py` so **`process_due_campaign_contacts_task`** runs every minute (it targets the marketing queue).
4. **Broker** (Redis/RabbitMQ) sized for peak queue depth; monitor lag on **both** transactional and marketing queues.
5. **Database:** PostgreSQL healthy; `CampaignContact` and `MessageLog` growth monitored; indexes as per migrations.
6. **Email:** Production SMTP / Workspace / relay credentials; **separate sending domain or envelope** for marketing vs transactional if possible.
7. **SMS:** Valid Fast2SMS credentials; **DLT templates** registered and matching variable format; monitor `return` codes in logs.
8. **Observability:** Alerts on queue depth, task failure rate, `MessageLog` spike in `FAILED`, and Gmail/Fast2SMS dashboard errors.
9. **Runbooks:** Pause campaign (`POST .../pause/`), inspect `GET .../status/` and message logs, `reset-contacts` only when safe (draft/paused).

---

## 9. Interaction with transactional and auth messaging

### 9.1 Celery queue separation (implemented)

**`apps.messaging.tasks.*`** routes to **`marketing-campaign-queue`** (production) or **`dev-marketing-campaign-queue`** (when `ENVIRONMENT=dev`). **OTP, booking, hotel, org, and flight** notification tasks stay on **`email-send-queue`** / **`dev-email-send-queue`**.

That means a **deep campaign backlog** no longer sits in the **same broker queue** as transactional tasks, so workers that **only** consume `email-send-queue` keep processing OTP and confirmations even while the marketing queue is long.

**Remaining caveats:**

- A **single worker process** subscribed to **both** queues can still spend time on campaign batches; for the strongest isolation, run **dedicated worker pools** (or containers) per queue.
- There is still **no intra-queue priority** (e.g. “OTP before booking email”) on the transactional queue.
- **Separate provider accounts** (Gmail/Workspace senders, Fast2SMS keys) for marketing vs transactional still help **quotas and reputation** (see below).

### 9.2 Shared Gmail SMTP identity

If campaigns and transactional mail use the **same** `EMAIL_HOST_USER` / SMTP config:

- **Quota and throttling** apply to the **combined** volume.
- **Reputation risk** is shared; a bad campaign list can hurt **OTP deliverability**.

### 9.3 Shared Fast2SMS / DLT footprint

Campaign SMS uses the same **`send_template_sms`** stack as many **booking** paths. Large blasts can:

- Consume **daily/API quota**.
- Trigger **rate limits** or errors that also affect **transactional** SMS if credentials are shared.

### 9.4 Jio DLT and template sprawl

Marketing templates must be **registered and approved**; using unapproved templates or wrong variable ordering fails loudly. Operational mistake can be mistaken for “system down” for SMS.

---

## 10. Other concerns

| Topic | Notes |
|-------|--------|
| **Security** | API keys for Fast2SMS and SMTP must stay in env/secrets; rotate on leak. |
| **Data protection** | Large exports and logs contain PII; restrict admin and log retention. |
| **Compliance** | Opt-out (`opt_out_sms` / `opt_out_email`) and blacklist are enforced in `send_*_for_campaign_contact`; still align with local marketing law (e.g. consent records). |
| **Multi-step campaigns** | Later steps depend on earlier scheduling math and Beat; partial failures leave a **mixed** funnel—use status endpoints and logs. |
| **Initial 10k cap** | Very large same-minute sends may need **multiple Beat cycles** or a future change to raise caps intentionally. |
| **Future code improvements** (not implemented) | Retries with idempotency keys, rate limiting, optional priority within transactional queue, dedicated transactional vs marketing providers by default. |

---

## 11. Related documents

- [`Messaging_Campaigns_Operations_Guide.md`](./Messaging_Campaigns_Operations_Guide.md) — operator-facing flows and endpoints.
- [`README.md`](../README.md) — Celery worker and Beat commands.
- Code references: `IDBOOKAPI/IDBOOKAPI/celery.py`, `apps/messaging/tasks.py`, `apps/messaging/services.py`, `apps/sms_gateway/mixins/fastwosms_mixins.py`.

---

*Document version: aligned with codebase patterns as of authoring; re-validate against `celery.py` and `tasks.py` after deployments that change queues or beat schedules.*
