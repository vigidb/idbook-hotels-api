# Flight Booking SMS Implementation Summary

## Overview

This document summarizes the SMS notification implementation for flight booking scenarios. All required SMS notification handlers have been added to the codebase.

## Implementation Status

### ✅ Completed Implementations

#### 1. SMS Notification Handlers Added (`apps/booking/tasks.py`)

All 10 SMS notification types have been implemented in the `send_booking_sms_task` function:

1. **FLIGHT_BOOKING_CONFIRMATION** ✅ (Already existed, verified)
   - Variables: `customer_name|origin-destination|booking_id`
   - Triggered: When booking is confirmed after payment

2. **FLIGHT_BOOKING_CANCEL** ✅ (Already existed, verified)
   - Variables: `customer_name|booking_id|refund_amount`
   - Triggered: When booking is cancelled

3. **FLIGHT_BOOKING_RESCHEDULED** ✅ (NEW)
   - Variables: `customer_name|booking_id|new_departure_datetime`
   - Triggered: When reschedule is successful
   - Location: `apps/booking/utils/flight_booking_utils.py` → `process_reschedule_success()`

4. **FLIGHT_BOOKING_FAILED** ✅ (NEW)
   - Variables: `customer_name|failure_reason|refund_amount`
   - Triggered: When payment fails for flight booking
   - Location: `apps/booking/utils/flight_payment_utils.py` → `FlightPaymentCallbackProcessor.process_phonepe_callback()`

5. **FLIGHT_SERVICES_ADDED** ✅ (NEW)
   - Variables: `customer_name|booking_id|additional_charge`
   - Triggered: When SSR (ancillary services) are successfully added
   - Location: `apps/booking/utils/flight_booking_utils.py` → `process_ssr_success()`

6. **FLIGHT_HOLD_BOOKING** ✅ (NEW)
   - Variables: `customer_name|booking_id|hold_expiry_datetime`
   - Triggered: When system places booking on hold
   - Note: Can be triggered manually if needed

7. **FLIGHT_HOLD_CANCELLED** ✅ (NEW)
   - Variables: `customer_name|booking_id|cancellation_reason`
   - Triggered: When hold booking expires or is cancelled by system
   - Note: Needs to be called when hold expires (can be added to a scheduled task)

8. **FLIGHT_HOLD_REQUESTED** ✅ (NEW)
   - Variables: `customer_name|booking_id|hold_expiry_datetime`
   - Triggered: When customer requests to hold booking
   - Location: `apps/booking/subviews/enhanced_flight_viewset.py` → `_create_booking_with_airiq()`

9. **FLIGHT_TICKET_ISSUED** ✅ (Already existed, updated to use airline PNR)
   - Variables: `customer_name|flight_route|pnr`
   - Triggered: When ticket is issued
   - Updated: Now uses `airline_pnr` instead of `booking.reference_code`

10. **CUSTOMER_FLIGHT_HOLD_CANCELLED** ✅ (NEW)
    - Variables: `customer_name|booking_id|booking_url`
    - Triggered: When customer cancels their hold booking
    - Note: Needs to be called when customer cancels hold booking via API

### Code Changes Made

#### 1. `apps/booking/tasks.py`
- Added 7 new SMS notification handlers:
  - `FLIGHT_BOOKING_RESCHEDULED`
  - `FLIGHT_BOOKING_FAILED`
  - `FLIGHT_SERVICES_ADDED`
  - `FLIGHT_HOLD_BOOKING`
  - `FLIGHT_HOLD_CANCELLED`
  - `FLIGHT_HOLD_REQUESTED`
  - `CUSTOMER_FLIGHT_HOLD_CANCELLED`
- Updated `FLIGHT_TICKET_ISSUED` to use airline PNR

#### 2. `apps/booking/utils/flight_booking_utils.py`
- Added SMS notification in `process_reschedule_success()` for reschedule confirmations
- Added SMS notification in `process_ssr_success()` for SSR services added
- Updated hold expiry parsing logic

#### 3. `apps/booking/utils/flight_payment_utils.py`
- Updated payment failure handler to use `FLIGHT_BOOKING_FAILED` instead of generic `PAYMENT_FAILED_INFO`

#### 4. `apps/booking/subviews/enhanced_flight_viewset.py`
- Added SMS notification when hold booking is created (`FLIGHT_HOLD_REQUESTED`)

## Next Steps Required

### 1. Database Setup ⚠️ REQUIRED

**Action Required**: Add SMS templates to the database

1. Register all 10 templates with Fast2SMS DLT portal
2. Get `message_id` for each approved template
3. Add templates to `MessageTemplate` model using Django admin or shell

**Template Codes to Add**:
- `FLIGHT_BOOKING_CONFIRMATION` (may already exist)
- `FLIGHT_BOOKING_CANCEL` (may already exist)
- `FLIGHT_BOOKING_RESCHEDULED` ⚠️ NEW
- `FLIGHT_BOOKING_FAILED` ⚠️ NEW
- `FLIGHT_SERVICES_ADDED` ⚠️ NEW
- `FLIGHT_HOLD_BOOKING` ⚠️ NEW
- `FLIGHT_HOLD_CANCELLED` ⚠️ NEW
- `FLIGHT_HOLD_REQUESTED` ⚠️ NEW
- `FLIGHT_TICKET_ISSUED` (may already exist)
- `CUSTOMER_FLIGHT_HOLD_CANCELLED` ⚠️ NEW

**Quick Setup Script**:
```python
from apps.org_resources.models import MessageTemplate

templates = [
    {
        'message_id': 'YOUR_MESSAGE_ID_HERE',
        'template_code': 'FLIGHT_BOOKING_RESCHEDULED',
        'template_message': 'Dear {#var#}, your flight booking {#var#} has been rescheduled. New departure: {#var#}. Check updated details in your account. Thank you, Idbook hotels'
    },
    # ... add all other templates
]

for template in templates:
    MessageTemplate.objects.update_or_create(
        template_code=template['template_code'],
        defaults={
            'message_id': template['message_id'],
            'template_message': template['template_message']
        }
    )
```

### 2. Additional Integration Points (Optional Enhancements)

#### A. Hold Booking Expiry Notification
**Location**: Create a scheduled task or add to existing expiry check

```python
# In a scheduled task or management command
from apps.booking.models import FlightBooking
from apps.booking.tasks import send_booking_sms_task
from django.utils import timezone

expired_holds = FlightBooking.objects.filter(
    status='HELD',
    hold_expires_at__lt=timezone.now()
)

for flight_booking in expired_holds:
    flight_booking.status = 'EXPIRED'
    flight_booking.save()
    
    send_booking_sms_task.delay(
        notification_type='FLIGHT_HOLD_CANCELLED',
        params={
            'booking_id': flight_booking.booking.id,
            'cancellation_reason': 'payment timeout'
        }
    )
```

#### B. Customer Hold Cancellation API
**Location**: Add to flight booking viewset

When customer cancels their hold booking via API, call:
```python
send_booking_sms_task.delay(
    notification_type='CUSTOMER_FLIGHT_HOLD_CANCELLED',
    params={
        'booking_id': booking.id,
        'booking_url': 'https://idbk.in/flights'
    }
)
```

### 3. Testing Checklist

- [ ] Test booking confirmation SMS
- [ ] Test cancellation SMS with refund amount
- [ ] Test reschedule SMS with new departure time
- [ ] Test payment failure SMS
- [ ] Test SSR services added SMS
- [ ] Test hold booking requested SMS
- [ ] Test hold booking cancelled SMS (expiry)
- [ ] Test customer hold cancellation SMS
- [ ] Test ticket issued SMS with airline PNR
- [ ] Verify all SMS variables are correctly formatted
- [ ] Check SMS logs in `SmsNotificationLog`
- [ ] Verify notifications are created in `UserNotification`

### 4. Current SMS Flow

#### Booking Confirmation Flow
```
Payment Success → handle_flight_payment_success() 
  → FlightPaymentProcessor._confirm_flight_booking()
  → _send_booking_notifications()
  → send_flight_booking_task('confirmed')
  → send_booking_sms_task('FLIGHT_BOOKING_CONFIRMATION')
```

#### Cancellation Flow
```
Cancel Booking → FlightCancellationManager.cancel_booking()
  → _send_cancellation_notifications()
  → send_flight_booking_task('cancelled')
  → send_booking_sms_task('FLIGHT_BOOKING_CANCEL')
```

#### Reschedule Flow
```
Reschedule Success → process_reschedule_success()
  → send_booking_sms_task('FLIGHT_BOOKING_RESCHEDULED')
```

#### SSR Services Flow
```
SSR Payment Success → process_ssr_success()
  → send_booking_sms_task('FLIGHT_SERVICES_ADDED')
```

#### Hold Booking Flow
```
Create Hold Booking → _create_booking_with_airiq(block_pnr=True)
  → send_booking_sms_task('FLIGHT_HOLD_REQUESTED')
```

#### Payment Failure Flow
```
Payment Failure → FlightPaymentCallbackProcessor.process_phonepe_callback()
  → send_booking_sms_task('FLIGHT_BOOKING_FAILED')
```

## Template Variable Format

All SMS templates use pipe-separated variables:
```
variables_values = "var1|var2|var3"
```

Example:
```python
variables_values = f"{customer_name}|{booking_id}|{refund_amount}"
```

## Important Notes

1. **Template Registration**: All templates must be registered and approved in Fast2SMS DLT before they can be used
2. **Variable Order**: Variable order must match exactly with the template registered in Fast2SMS
3. **Date Formatting**: Dates are formatted as `'%B %d, %Y %I:%M %p'` (e.g., "May 20, 2025 10:30 AM")
4. **Error Handling**: All SMS sending is wrapped in try-except blocks to prevent booking failures
5. **Logging**: SMS sending errors are logged but don't fail the main operation

## Files Modified

1. `IDBOOKAPI/apps/booking/tasks.py` - Added 7 new SMS handlers
2. `IDBOOKAPI/apps/booking/utils/flight_booking_utils.py` - Added SMS calls for reschedule and SSR
3. `IDBOOKAPI/apps/booking/utils/flight_payment_utils.py` - Updated payment failure SMS
4. `IDBOOKAPI/apps/booking/subviews/enhanced_flight_viewset.py` - Added hold booking SMS
5. `docs/FLIGHT_SMS_TEMPLATES_SETUP_GUIDE.md` - Comprehensive setup guide (NEW)
6. `docs/FLIGHT_SMS_IMPLEMENTATION_SUMMARY.md` - This file (NEW)

## Support

For issues or questions:
1. Check SMS logs in `SmsNotificationLog` model
2. Verify template exists in `MessageTemplate` model
3. Check Fast2SMS dashboard for delivery status
4. Review Django logs for error messages

