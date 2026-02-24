# Custom Agent Commission/Markup Per Booking

Agents can send a **custom commission (markup)** for a **particular booking** instead of using their default markup from Agent Markup Config. This is supported for both **hotel** and **flight** bookings.

## Optional request body fields

Send **one** of these in the **same request body** as the booking (e.g. alongside hotel/flight payload). If **none** are sent, the agent's default markup (from Agent Markup Config) is used. If **any** are sent, that value applies to **this booking only**.

| Field | Type | Description |
|-------|------|-------------|
| `agent_markup_override` | object | `{ "percent": 5 }` for 5% markup, or `{ "amount": 100 }` for a fixed amount (e.g. INR 100). |
| `agent_markup_percent` | number | Override with a percentage (e.g. `5` for 5%). Used if `agent_markup_override` is not sent. |
| `agent_markup_amount` | number | Override with a fixed amount. Used if `agent_markup_override` and `agent_markup_percent` are not sent. |

**Full request example (hotel pre-confirm with 5% custom markup):**
```json
{
  "check_in": "2025-02-01",
  "check_out": "2025-02-03",
  "rooms": [ ... ],
  "guest_details": { ... },
  "agent_markup_percent": 5
}
```
Or using the object form:
```json
{
  "check_in": "2025-02-01",
  "check_out": "2025-02-03",
  "rooms": [ ... ],
  "guest_details": { ... },
  "agent_markup_override": { "percent": 5 }
}
```

## Where it applies

- **Hotel pre-confirm:** `POST /api/v1/booking/hotel/pre-confirm/` — add the field to the request body.
- **Hotel create (search-booking):** `POST /api/v1/booking/` with hotel payload — add the field to the request body.
- **Flight create-booking:** Enhanced flight create-booking endpoint — add the field to the request body.

## Examples

**Percentage for this booking:**
```json
"agent_markup_override": { "percent": 5 }
```
or
```json
"agent_markup_percent": 5
```

**Fixed amount for this booking:**
```json
"agent_markup_override": { "amount": 250 }
```
or
```json
"agent_markup_amount": 250
```

## Code reference

- `apps/booking/utils/markup_utils.AgentMarkupCalculator.get_agent_markup(agent_id, base_amount, markup_override=None, request_or_data=None)` — computes markup; if `request_or_data` is provided (request or data dict) and `markup_override` is not, override is read from request/data (fields: `agent_markup_override`, `agent_markup_percent`, `agent_markup_amount`). Used in hotel pre-confirm, hotel create, and enhanced flight create-booking.
