# Manual Refund API

Used when payment was collected but the booking failed (e.g. flight booking failure after payment) or when automatic refund did not run or failed. Supports **Wallet (Idbook)** and **Razorpay**. PhonePe refunds must be done via the booking cancel flow or the payment gateway dashboard.

## API Endpoint

**POST** `/api/v1/booking/bookings/<booking_id>/refund/`

- **Permission:** Staff/Admin only (`IsAdminUser`).
- **Auth:** Required (e.g. JWT).

### Request body (optional)

```json
{
  "amount": "1500.00",
  "reason": "Flight booking failed after payment (AirIQ error)"
}
```

- `amount` (optional): Refund amount. If omitted, full payment amount is refunded.
- `reason` (optional): Stored in refund notes (e.g. for Razorpay).

### Responses

**Success (Wallet or Razorpay initiated):**

- `200`: `{ "status": "success", "message": "Refund initiated successfully (...)", "data": { ... } }`

**Errors:**

- `404`: Booking not found.
- `400`: Already refunded / no payment found / invalid amount / payment method requires gateway (e.g. PhonePe).

## Django Admin

1. Go to **Booking** list in admin.
2. Select one or more bookings.
3. Choose action **"Trigger manual refund"** and click **Go**.

Same logic as the API: supports Wallet and Razorpay; shows success or error per booking.

## Behaviour

- Uses the latest **successful** payment for the booking (ignores existing refund records).
- If the booking already has a successful refund, returns "Already refunded".
- **Wallet:** Credits amount back to user wallet, creates refund payment record and log, sets booking status to `refunded` and (for flights) `flight_booking.status` to `REFUNDED`.
- **Razorpay:** Creates refund log, calls Razorpay refund API, updates booking status. Refund may complete asynchronously (webhook can update status later).
- **PhonePe:** Not supported by this flow; use cancel booking or gateway dashboard.
