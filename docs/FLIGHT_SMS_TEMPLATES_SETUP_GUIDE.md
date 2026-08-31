# Flight Booking SMS Templates Setup Guide

This guide explains how to set up and manage SMS templates for flight booking scenarios in the IDBook system.

## Overview

The SMS system uses Fast2SMS DLT (Distributed Ledger Technology) templates. Each SMS template must be:
1. Registered with Fast2SMS and approved by DLT
2. Added to the `MessageTemplate` model in the database
3. Integrated into the code at appropriate notification points

## SMS Template System Architecture

### Components

1. **MessageTemplate Model** (`apps/org_resources/models.py`)
   - Stores template code and Fast2SMS message_id mapping
   - Fields: `message_id`, `template_code`, `template_message`

2. **SMS Sending Function** (`apps/sms_gateway/mixins/fastwosms_mixins.py`)
   - `send_template_sms(mobile_number, template_code, variables_values)`
   - Uses pipe-separated `variables_values` format: `var1|var2|var3`

3. **SMS Task Handler** (`apps/booking/tasks.py`)
   - `send_booking_sms_task(notification_type, params)`
   - Routes different notification types to appropriate template codes

## Required SMS Templates

### 1. Flight Booking Confirmation ✅ (Already Implemented)
- **Template Code**: `FLIGHT_BOOKING_CONFIRMATION`
- **Variables**: `{customer_name}|{origin}|{destination}|{booking_id}`
- **Example**: `Amit Patel|Delhi|Mumbai|IDBFLT123456`
- **Template Message**: 
  ```
  Dear {#var#}, your flight from {#var#} to {#var#} is confirmed. Booking ID: {#var#}. Check-in 3hrs before departure. Thank you, Idbook hotels
  ```
- **Triggered**: When flight booking is confirmed after payment

### 2. Flight Booking Cancellation ✅ (Already Implemented)
- **Template Code**: `FLIGHT_BOOKING_CANCEL`
- **Variables**: `{customer_name}|{booking_id}|{refund_amount}`
- **Example**: `Amit Patel|IDBFLT123456|4,500`
- **Template Message**:
  ```
  Dear {#var#}, your flight booking {#var#} has been cancelled. Refund of Rs.{#var#} will be processed within 5-7 working days. Thank you, Idbook hotels
  ```
- **Triggered**: When flight booking is cancelled

### 3. Flight Booking Rescheduled ❌ (Needs Implementation)
- **Template Code**: `FLIGHT_BOOKING_RESCHEDULED`
- **Variables**: `{customer_name}|{booking_id}|{new_departure_datetime}`
- **Example**: `Amit Patel|IDBFLT123456|May 20, 2025 10:30 AM`
- **Template Message**:
  ```
  Dear {#var#}, your flight booking {#var#} has been rescheduled. New departure: {#var#}. Check updated details in your account. Thank you, Idbook hotels
  ```
- **Triggered**: When flight booking is successfully rescheduled

### 4. Flight Booking Failed ❌ (Needs Update)
- **Template Code**: `FLIGHT_BOOKING_FAILED`
- **Variables**: `{customer_name}|{failure_reason}|{refund_amount}`
- **Example**: `Amit Patel|payment gateway error|8,500`
- **Template Message**:
  ```
  Dear {#var#}, your flight booking attempt has failed due to {#var#}. If amount was deducted, refund of Rs.{#var#} will be processed within 5-7 working days. Thank you, Idbook hotels
  ```
- **Triggered**: When flight booking payment fails

### 5. SSR Services Added ❌ (Needs Implementation)
- **Template Code**: `FLIGHT_SERVICES_ADDED`
- **Variables**: `{customer_name}|{booking_id}|{additional_charge}`
- **Example**: `Amit Patel|IDBFLT123456|2,450`
- **Template Message**:
  ```
  Dear {#var#}, special services have been added to your flight booking {#var#}. Total additional charge: Rs.{#var#}. View details in your account. Thank you, Idbook hotels
  ```
- **Triggered**: When SSR (ancillary services) are successfully added

### 6. Hold Booking Confirmation ❌ (Needs Implementation)
- **Template Code**: `FLIGHT_HOLD_BOOKING`
- **Variables**: `{customer_name}|{booking_id}|{hold_expiry_datetime}`
- **Example**: `Amit Patel|IDBFLT123456|May 15, 2025 11:59 PM`
- **Template Message**:
  ```
  Dear {#var#}, your flight booking {#var#} is on hold until {#var#}. Complete payment to confirm your reservation. Thank you, Idbook hotels
  ```
- **Triggered**: When booking is placed on hold (system-initiated)

### 7. Hold Booking Cancelled ❌ (Needs Implementation)
- **Template Code**: `FLIGHT_HOLD_CANCELLED`
- **Variables**: `{customer_name}|{booking_id}|{cancellation_reason}`
- **Example**: `Amit Patel|IDBFLT123456|payment timeout`
- **Template Message**:
  ```
  Dear {#var#}, your hold booking {#var#} has been cancelled due to {#var#}. Please book again if needed. Thank you, Idbook hotels
  ```
- **Triggered**: When hold booking expires or is cancelled by system

### 8. Customer Initiated Hold Booking ❌ (Needs Implementation)
- **Template Code**: `FLIGHT_HOLD_REQUESTED`
- **Variables**: `{customer_name}|{booking_id}|{hold_expiry_datetime}`
- **Example**: `Amit Patel|IDBFLT123456|May 15, 2025 6:00 PM`
- **Template Message**:
  ```
  Dear {#var#}, your flight has been placed on hold (ID: {#var#}) until {#var#}. Complete payment before expiry to confirm booking. Thank you, Idbook hotels
  ```
- **Triggered**: When customer requests to hold booking

### 9. Flight Ticket Issued ✅ (Already Implemented)
- **Template Code**: `FLIGHT_TICKET_ISSUED`
- **Variables**: `{customer_name}|{flight_route}|{pnr}`
- **Example**: `Amit Patel|Delhi-Mumbai|ABC123DEF`
- **Template Message**:
  ```
  Dear {#var#}, your flight ticket for {#var#} has been issued. PNR: {#var#}. Download your e-ticket from your account. Thank you, Idbook hotels
  ```
- **Triggered**: When flight ticket is issued

### 10. Customer Cancelled Hold Booking ❌ (Needs Implementation)
- **Template Code**: `CUSTOMER_FLIGHT_HOLD_CANCELLED`
- **Variables**: `{customer_name}|{booking_id}|{booking_url}`
- **Example**: `Amit Patel|IDBFLT123456|https://idbk.in/flights`
- **Template Message**:
  ```
  Dear {#var#}, your hold booking {#var#} has been cancelled as per your request. No charges applied. Book again anytime: {#var#}. Thank you, Idbook hotels
  ```
- **Triggered**: When customer cancels their hold booking

## Database Setup

### Step 1: Register Templates with Fast2SMS

1. Log in to Fast2SMS dashboard
2. Navigate to DLT Template section
3. Register each template with the exact message format
4. Wait for DLT approval
5. Note down the `message_id` for each approved template

### Step 2: Add Templates to Database

Use Django admin or Django shell to add templates:

```python
from apps.org_resources.models import MessageTemplate

templates = [
    {
        'message_id': '203246',  # From Fast2SMS
        'template_code': 'FLIGHT_BOOKING_CONFIRMATION',
        'template_message': 'Dear {#var#}, your flight from {#var#} to {#var#} is confirmed. Booking ID: {#var#}. Check-in 3hrs before departure. Thank you, Idbook hotels'
    },
    {
        'message_id': '203239',
        'template_code': 'FLIGHT_BOOKING_CANCEL',
        'template_message': 'Dear {#var#}, your flight booking {#var#} has been cancelled. Refund of Rs.{#var#} will be processed within 5-7 working days. Thank you, Idbook hotels'
    },
    {
        'message_id': '203244',
        'template_code': 'FLIGHT_BOOKING_RESCHEDULED',
        'template_message': 'Dear {#var#}, your flight booking {#var#} has been rescheduled. New departure: {#var#}. Check updated details in your account. Thank you, Idbook hotels'
    },
    {
        'message_id': '203238',
        'template_code': 'FLIGHT_BOOKING_FAILED',
        'template_message': 'Dear {#var#}, your flight booking attempt has failed due to {#var#}. If amount was deducted, refund of Rs.{#var#} will be processed within 5-7 working days. Thank you, Idbook hotels'
    },
    {
        'message_id': '203245',
        'template_code': 'FLIGHT_SERVICES_ADDED',
        'template_message': 'Dear {#var#}, special services have been added to your flight booking {#var#}. Total additional charge: Rs.{#var#}. View details in your account. Thank you, Idbook hotels'
    },
    {
        'message_id': '203237',
        'template_code': 'FLIGHT_HOLD_BOOKING',
        'template_message': 'Dear {#var#}, your flight booking {#var#} is on hold until {#var#}. Complete payment to confirm your reservation. Thank you, Idbook hotels'
    },
    {
        'message_id': '203243',
        'template_code': 'FLIGHT_HOLD_CANCELLED',
        'template_message': 'Dear {#var#}, your hold booking {#var#} has been cancelled due to {#var#}. Please book again if needed. Thank you, Idbook hotels'
    },
    {
        'message_id': '203240',
        'template_code': 'FLIGHT_HOLD_REQUESTED',
        'template_message': 'Dear {#var#}, your flight has been placed on hold (ID: {#var#}) until {#var#}. Complete payment before expiry to confirm booking. Thank you, Idbook hotels'
    },
    {
        'message_id': '203242',
        'template_code': 'FLIGHT_TICKET_ISSUED',
        'template_message': 'Dear {#var#}, your flight ticket for {#var#} has been issued. PNR: {#var#}. Download your e-ticket from your account. Thank you, Idbook hotels'
    },
    {
        'message_id': '203241',
        'template_code': 'CUSTOMER_FLIGHT_HOLD_CANCELLED',
        'template_message': 'Dear {#var#}, your hold booking {#var#} has been cancelled as per your request. No charges applied. Book again anytime: {#var#}. Thank you, Idbook hotels'
    },
]

for template in templates:
    MessageTemplate.objects.update_or_create(
        template_code=template['template_code'],
        defaults={
            'message_id': template['message_id'],
            'template_message': template['template_message']
        }
    )
    print(f"Created/Updated template: {template['template_code']}")
```

### Step 3: Verify Templates

Check templates in Django admin:
- Navigate to: `/admin/org_resources/messagetemplate/`
- Verify all templates are present with correct `message_id` values

## Code Integration Points

### Current Implementation Status

| Template | Status | Location |
|----------|--------|----------|
| FLIGHT_BOOKING_CONFIRMATION | ✅ Implemented | `send_booking_sms_task` line 479 |
| FLIGHT_BOOKING_CANCEL | ✅ Implemented | `send_booking_sms_task` line 504 |
| FLIGHT_TICKET_ISSUED | ✅ Implemented | `send_booking_sms_task` line 525 |
| FLIGHT_BOOKING_RESCHEDULED | ❌ Missing | Needs implementation |
| FLIGHT_BOOKING_FAILED | ⚠️ Partial | Uses generic PAYMENT_FAILED_INFO |
| FLIGHT_SERVICES_ADDED | ❌ Missing | Needs implementation |
| FLIGHT_HOLD_BOOKING | ❌ Missing | Needs implementation |
| FLIGHT_HOLD_CANCELLED | ❌ Missing | Needs implementation |
| FLIGHT_HOLD_REQUESTED | ❌ Missing | Needs implementation |
| CUSTOMER_FLIGHT_HOLD_CANCELLED | ❌ Missing | Needs implementation |

### Where SMS Notifications Are Triggered

1. **Booking Confirmation**: 
   - `apps/booking/utils/flight_payment_utils.py` → `_send_booking_notifications()` line 921
   - `apps/booking/utils/flight_booking_utils.py` → `_send_booking_notifications()` line 1254

2. **Cancellation**:
   - `apps/booking/utils/flight_booking_utils.py` → `_send_cancellation_notifications()` line 1465

3. **Ticket Issued**:
   - `apps/booking/utils/flight_booking_utils.py` → `send_flight_ticket_notification()` line 1489

4. **Payment Failed**:
   - `apps/booking/utils/flight_payment_utils.py` → `FlightPaymentCallbackProcessor.process_phonepe_callback()` line 1433

5. **Reschedule** (Needs Implementation):
   - Should be added in `process_reschedule_success()` function

6. **SSR Services** (Needs Implementation):
   - Should be added in `process_ssr_success()` function

7. **Hold Bookings** (Needs Implementation):
   - Should be added when hold booking is created/expired/cancelled

## Testing

### Test Each Template

1. Create test bookings for each scenario
2. Verify SMS is sent with correct variables
3. Check SMS logs in `SmsNotificationLog` model
4. Verify notifications are created in `UserNotification` model

### Test Commands

```python
# Test booking confirmation
from apps.booking.tasks import send_booking_sms_task
send_booking_sms_task.delay('FLIGHT_BOOKING_CONFIRMATION', {'booking_id': 123})

# Test cancellation
send_booking_sms_task.delay('FLIGHT_BOOKING_CANCEL', {'booking_id': 123, 'refund_amount': 4500})

# Test reschedule (after implementation)
send_booking_sms_task.delay('FLIGHT_BOOKING_RESCHEDULED', {
    'booking_id': 123,
    'new_departure': 'May 20, 2025 10:30 AM'
})
```

## Troubleshooting

### Common Issues

1. **Template not found**
   - Check `MessageTemplate` table for template_code
   - Verify `message_id` is correct

2. **SMS not sending**
   - Check Fast2SMS API key in settings
   - Verify DLT sender ID
   - Check `SmsNotificationLog` for error responses

3. **Wrong variables**
   - Verify variable order matches template
   - Check pipe-separated format: `var1|var2|var3`

4. **Template not approved**
   - Ensure template is approved in Fast2SMS DLT
   - Wait for approval before using in production

## Next Steps

1. ✅ Review this guide
2. ⏳ Register templates with Fast2SMS
3. ⏳ Add templates to database
4. ⏳ Implement missing notification handlers
5. ⏳ Update code to trigger notifications
6. ⏳ Test all scenarios
7. ⏳ Deploy to production

