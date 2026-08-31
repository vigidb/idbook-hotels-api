# Messaging campaigns — operations guide

This guide is for **operators** (marketing, growth, CRM) and **engineers** who wire Idbook’s email/SMS journeys end to end.

## Mental model

1. **Contacts** are the audience pool (segmentation: `group_type`, optional `city` / `country` on the campaign).
2. A **campaign** holds targeting + lifecycle **status**; **steps** define channel, template, optional **delivery provider**, delay, and active flag.
3. **Schedule / send now** enqueues work: `CampaignContact` rows are created and processed asynchronously (Celery). **Message logs** capture provider outcomes per send.

---

## 1. Choosing a contact list (audience)

**How “audience group” works**

1. **`target_group_type`** (optional) — same value as `Contact.group_type` (e.g. `B2C-GRP`). If omitted or blank, **all group types** are considered (still narrowed by other filters).
2. **`target_filters`** (JSON on the campaign) — extra narrowing:
   - **`city`**, **`country`** — case-insensitive exact match on `Contact.city` / `Contact.country`.
   - **`tags`** (alias: **`segment_tags`**) — list of strings (or comma-separated in CSV-oriented tooling). Compared to `Contact.segment_tags` (stored as a JSON array of **lowercase** strings).
   - **`tags_match`** — `"any"` (default) = contact must have **at least one** of the listed tags; `"all"` = contact must have **every** listed tag.

| UI / API | What it does |
|----------|----------------|
| **Target group type** | Restricts to one `Contact.group_type`. Empty = all groups (plus filters). |
| **City / country / tags** (`target_filters`) | See above. |
| **POST** `/api/v1/messaging/campaigns/audience-preview/` | Body includes `target_group_type` and `target_filters` → `{ "count": N, ... }`. |
| **GET** `/api/v1/messaging/campaigns/{id}/audience/` | Same for a saved campaign. |

**Tag storage:** New uploads and API writes normalize tags to **lowercase** so campaign filters stay consistent. Older contacts with mixed-case tags may need a one-off cleanup or re-upload.

**Operations tip:** Always confirm **count > 0** before schedule/send. Empty audiences are blocked at `schedule` and `send_now`.

**CSV upload:** A column **`tags`** (or **`segment_tags`**, `labels`) may contain comma-separated labels (e.g. `vip, ota`). On **create**, those tags are stored on the contact. On **update** (same phone/email + group), new tags are **merged** with existing `segment_tags` (union, then normalized).

---

## 2. Templates

| Channel | What to enter in `template_code` | Where it is validated |
|---------|----------------------------------|------------------------|
| **Email** | Active **EmailTemplate.slug** with **`is_marketing=true`** | `CampaignStep` validation (non-marketing / transactional email templates are not allowed on campaign steps). |
| **SMS** | Active **MessageTemplate** with DLT type **`service_explicit`** or **`promotional`** only | `CampaignStep` validation (`transactional` and **`service_implicit`** are excluded from campaigns — OTP / service-implicit flows stay off bulk journeys). |

**DLT SMS template types** (on `MessageTemplate`): `transactional` (bank OTP / direct debit-credit alerts), `service_implicit` (non-promo triggers: OTP from non-bank, order/delivery updates), `service_explicit` (consent-based promo to existing customers), `promotional` (marketing to prospects; DND rules apply). New SMS templates default to **`promotional`** in the admin UI.

| Endpoint | Purpose |
|----------|---------|
| `GET/POST/PATCH/DELETE /api/v1/messaging/email-templates/` | CRUD email templates; list supports search, filters, pagination, sort. |
| `GET/POST/PATCH/DELETE /api/v1/messaging/sms-templates/` | CRUD SMS `MessageTemplate` rows (same list features). |
| `GET /api/v1/messaging/sms-templates/?for_campaigns=1` | **Campaign picker only:** active templates whose type is **`service_explicit`** or **`promotional`**. |
| `GET /api/v1/messaging/email-templates/?is_marketing=true` | Campaign email picker: marketing templates only. |

---

## 3. Delivery providers

- Each step may set **`messaging_provider`** (FK to `MessagingProviderConfig`) matching the step **channel** (`email` vs `sms`).
- If omitted, resolution follows: template-level provider (email) → **default** row for channel → environment defaults.
- Configure under **Delivery providers** in the admin app or `GET/POST /api/v1/messaging/provider-configs/`.

---

## 4. Multi-step journeys

- Steps are ordered by **`order_index`** (unique per campaign).
- **`delay_amount` + `delay_unit`** apply **after the previous step’s base time** (or campaign start for step 1). The worker advances the base time as it builds `CampaignContact` rows.
- **`active: false`** skips step participation when contacts are enqueued.
- CRUD: `/api/v1/messaging/campaign-steps/?campaign={id}` (filter + paginated list).

**Guardrails:** `schedule` / `send_now` require at least one **active** step with a **non-empty** `template_code`.

---

## 5. Scheduling and execution

| Action | Endpoint | Notes |
|--------|----------|--------|
| **Schedule** | `POST .../campaigns/{id}/schedule/` body `{ "schedule_time": "<ISO-8601>" }` | Sets status `scheduled`, enqueues contact build. |
| **Send now** | `POST .../campaigns/{id}/send_now/` | `schedule_time = now`, status `running`. |
| **Pause** | `POST .../campaigns/{id}/pause/` | Status `paused`; edit audience/steps when allowed in UI. |
| **Reset pipeline rows** | `POST .../campaigns/{id}/reset-contacts/` | **Draft or paused only** — deletes `CampaignContact` rows for a clean rebuild. |

Ensure **Celery workers** consume the **marketing campaign queue** (`marketing-campaign-queue` in production, `dev-marketing-campaign-queue` when `ENVIRONMENT=dev`) for `enqueue_campaign_contacts_task` / batch send, and **beat** is running so `process_due_campaign_contacts_task` is scheduled on that same queue (see `IDBOOKAPI/celery.py` and [README](../README.md#celery)).

---

## 6. Viewing results in depth

| View | Endpoint | Use for |
|------|----------|---------|
| **Aggregate + per-step** | `GET .../campaigns/{id}/status/` | `counters` (pending, queued, sent, failed, skipped_opt_out, blacklisted), `steps[]` with per-step counters, `audience_count`. |
| **Per-recipient pipeline** | `GET .../campaigns/{id}/contacts/?status=&offset=&limit=` | `CampaignContact` + nested `contact` / `step`. |
| **Provider-level logs** | `GET .../message-logs/?campaign=&channel=&status=` | Individual sends, `provider_response` JSON. |

**Marketing / PM lens — “success” metrics**

- **Reach:** `audience_count` vs `counters.sent` (and per-step `sent`).
- **Health:** `failed` rate; inspect `message-logs` + `provider_response` for DLT/SMTP errors.
- **Compliance:** `skipped_opt_out` and `blacklisted` — expect non-zero on real lists; sudden spikes warrant list hygiene review.
- **Funnel timing:** compare per-step totals to detect steps that never drain (worker/provider issues).

---

## 7. Admin dashboard flows

1. **Campaigns** → New campaign → set audience → add steps (template + optional provider) → **Save**.
2. Open **campaign detail** → **Schedule** or **Send now**; watch **Steps & results** and **Recent message logs**; **Open full logs** for deep debugging.
3. **Edit** (draft/paused) adjusts targeting and steps; **Pause** first if the campaign is active.

---

## 8. Architecture notes (engineering)

- **List performance:** `CampaignViewSet` annotates `step_count`, `select_related(created_by)`, `prefetch_related(steps)` for list/detail.
- **Status endpoint:** One aggregate query for global counters; one grouped query by `step_id` for step breakdown (avoids N+1 per step).
- **SMS templates** are managed via `SmsTemplateViewSet` (CRUD on `org_resources.MessageTemplate`). Campaign UIs call the list with **`for_campaigns`** so transactional and service-implicit templates never appear in step builders.

For edge cases and product scope, see `docs/PRD/Messaging-Edge-Cases-Coverage.md` and the messaging PRD in `docs/PRD/`.

For **dev vs production queues, batch limits, on-time delivery precision, duplicate behavior, volume tiers, Gmail/Fast2SMS/Jio DLT constraints, and shared-queue impact on transactional/auth messaging**, see [`Messaging_Scalability_Reliability_Production_Guide.md`](./Messaging_Scalability_Reliability_Production_Guide.md).
