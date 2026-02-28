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

- `amount` (optional): Refund amount. If omitted, the **total of all successful payments** for that booking is refunded (full amount paid).
- `reason` (optional): Refund reason. Stored in wallet transaction details, `BookingPaymentDetail.transaction_details.refund_reason`, refund logs (`BookingRefundLog` request), and Razorpay notes, so it appears correctly in payment history and admin.

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

- **Amount:** Sums **all successful (non-refund) payments** for the booking. If you omit `amount`, that total is refunded so the full amount paid is covered. If the booking had multiple Razorpay payments, each is refunded in turn.
- If the booking already has a successful refund, returns "Already refunded".
- **Reason:** The `reason` you send is stored in: wallet `WalletTransaction.transaction_details` and `BookingPaymentDetail.transaction_details.refund_reason`, `WalletTransactionLog.request.refund_reason`, and (for Razorpay) in the refund log request and Razorpay notes, so it appears in payment history and admin.
- **Wallet:** Credits the amount to the correct wallet (company / agent / user), creates refund payment record and log with reason, sets booking status to `refunded` and (for flights) `flight_booking.status` to `REFUNDED`.
- **Razorpay:** Refunds **every** successful Razorpay payment for the booking (one API call per payment), creates a refund log per payment with reason, updates booking status. Refunds may complete asynchronously (webhook can update status later).
- **PhonePe:** Not supported by this flow; use cancel booking or gateway dashboard.
