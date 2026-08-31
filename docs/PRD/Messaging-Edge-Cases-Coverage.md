# Messaging System – PRD Edge Case Coverage

This document maps **Section 9. Edge Case Handling** of the [Customer Engagement & Messaging Automation System](Customer%20Engagement%20%26%20Messaging%20Automation%20System.md) to the current implementation.

---

## 1. Data issues

| Edge case | Status | Implementation |
|-----------|--------|----------------|
| **Duplicate contacts** | Done | `upsert_contact_from_row` in `apps/messaging/services.py`: contacts matched by `(group_type, phone)` or `(group_type, email)`; create or update. CSV upload reports per-row errors. |
| **Invalid phone numbers** | Done | CSV upload validates phone: 10–15 digits (non-digits stripped). Invalid rows get row-level error in response. |
| **Invalid emails** | Done | CSV upload validates email with Django `EmailValidator`. Invalid rows get row-level error. |

---

## 2. Messaging issues

| Edge case | Status | Implementation |
|-----------|--------|----------------|
| **SMS provider failure** | Done | `send_sms_for_campaign_contact`: response/status checked; on failure `CampaignContact.status = FAILED`, `error_message` and `error_code` set; `MessageLog` created with failed status. |
| **Email bounce** | Not done | Would require SES SNS/webhook and logic to set `Contact.opt_out_email` or `is_blacklisted`. |
| **Template mismatch** | Done | Email: `render_template_string` wrapped in `try/except KeyError`; missing variable sets `CampaignContact.status = FAILED` and `error_message = "Template variable missing: …"`. SMS template validity is provider-side. |

---

## 3. Compliance

| Edge case | Status | Implementation |
|-----------|--------|----------------|
| **Opt-out** | Done | `Contact.opt_out_sms`, `opt_out_email`, `opt_out_whatsapp`. Checked before send; contact skipped with `CampaignContact.status = SKIPPED_OPT_OUT`. |
| **Unsubscribe** | Partial | No dedicated public unsubscribe endpoint. Contacts can be updated via PATCH `/api/v1/messaging/contacts/{id}/` (e.g. set `opt_out_email=true`). |
| **DLT template rules** | Not done | India SMS compliance (DLT registration, template approval) is not implemented; depends on provider and ops. |

---

## 4. Operational

| Edge case | Status | Implementation |
|-----------|--------|----------------|
| **Campaign pause** | Done | `Campaign.status = PAUSED`; `pause` action in viewset. Batch task still processes due contacts; pause stops new scheduling (run/schedule). |
| **Rate limiting** | Partial | `MessagingProviderConfig.rate_limit_per_minute` exists but is not enforced in send path. Batch size (100) limits concurrency. |
| **Retry mechanism** | Not done | Failed sends are not retried automatically. Could add Celery `retry` or a periodic task to re-queue FAILED with backoff. |

---

## 5. Other PRD alignment

- **Campaign send execution**: After `enqueue_campaign_contacts_task`, due `CampaignContact` rows are queued to `send_campaign_batch_task` (batches of 100). Celery Beat task `process_due_campaign_contacts_task` runs every minute to process scheduled (future) sends.
- **Encoding**: CSV upload tries UTF-8, then cp1252, then latin-1 to avoid decode errors on Excel-exported files.

---

## 6. Suggested next steps

1. **Rate limiting**: Use `MessagingProviderConfig.rate_limit_per_minute` in batch task (e.g. sleep or throttle sends per minute).
2. **Retry**: Add Celery `autoretry_for` on `send_campaign_batch_task` or a separate task to re-queue FAILED contacts with a cap.
3. **Unsubscribe**: Public endpoint (e.g. by token or email/phone) that sets `opt_out_*` without full auth.
4. **Email bounce**: SES SNS subscription + handler to update contact opt-out/blacklist.
5. **DLT**: Document provider-specific DLT requirements and any template/sender configuration.
