# Hotel Pre-Confirm Guest Details & Agent Filter by Customer

## 1. Hotel pre-confirm: how guest details are passed and linked to users

**Endpoint:** Hotel pre-confirm (e.g. `hotel_pre_confirm_booking` in `apps/booking/viewsets.py`).

### Request body fields used as guest details

| Body field         | Fallback / alias   | Purpose                         |
|--------------------|--------------------|---------------------------------|
| `guest_email`      | `email`            | Guest email (required if no user) |
| `guest_mobile`     | `mobile_number`    | Guest phone                     |
| `guest_name`       | `name`             | Guest name                      |
| `guest_country`    | `country`          | Guest country                   |
| `guest_state`      | `state`            | Guest state                     |
| `guest_gst`        | `gst`              | Guest GST                       |
| `guest_pan`        | `pan`              | Guest PAN                       |

### Unauthenticated (guest / B2C) flow

1. Guest details are taken from the request body using the fields above.
2. **Linking:** If `guest_email` or `guest_mobile` is present, the backend looks up an existing user by email, then by mobile if needed.
3. **If user found:** That user is set as `booking.user`; name/email/mobile may be updated.
4. **If not found and `guest_email` is set:** A new user is created via `create_user(...)` and `add_group_for_guest_user(user)`, and that user becomes `booking.user`.
5. **If not found and no email:** The API returns “Guest email is required”.

So for unauthenticated requests, guest fields decide who the booking user is (resolve or create by email/mobile), and that user is stored as `booking.user`.

### Authenticated agent flow

1. `booking.user` is always the **logged-in user** (the agent). It is not overwritten by guest fields.
2. Guest fields are still sent in the body as above (e.g. `guest_email`, `guest_mobile`, `guest_name`).
3. After the booking is created and the agent–booking link is set, the backend calls  
   `ensure_agent_contact_linked_as_customer(agent_detail, guest_email, guest_mobile, guest_name)`  
   using values from the request body (with fallbacks like `email`, `mobile_number`, `name`).
4. That creates or finds a **Customer** for that contact and links them to the agent as an agent customer (AGENT-CUST). It does **not** change `booking.user`; the booking stays on the agent.

So for agents, guest details are used only to create/link the contact as the agent’s customer for CRM, not to set the booking user.

### Code references

- Guest handling (unauthenticated): `apps/booking/viewsets.py`, ~lines 2040–2125, in `hotel_pre_confirm_booking`.
- Agent + guest contact linking: `apps/booking/viewsets.py`, ~2771–2790 and ~2796–2812, where `ensure_agent_contact_linked_as_customer` is called with `request.data.get("guest_email")` (and fallbacks).

---

## 2. Agent: filter bookings by a specific customer

An agent can restrict the booking list to one customer using **user id** or **customer id**.

### Option A: Agent dashboard bookings

**Endpoint:** `GET /api/v1/org-resources/agent-dashboard/bookings/`

**Query parameters:**

| Param         | Type   | Description |
|---------------|--------|-------------|
| `user_id`     | int    | Restrict to bookings where `booking.user_id` equals this User id. |
| `customer_id` | int    | Restrict to bookings for this Customer id. Resolved via `Customer` → `user_id`; only customers linked to the current agent are allowed. Ignored if `user_id` is also sent. |
| `status`      | string | Booking status filter (unchanged). |
| `booking_source` | string | Booking source filter (unchanged). |
| `start_date` / `end_date` | date | Date range on `created` (unchanged). |
| `offset` / `limit` | int | Pagination (unchanged). |

**Example:**  
`GET /api/v1/org-resources/agent-dashboard/bookings/?user_id=123`  
→ Only bookings for User id 123 that belong to this agent (either `booking.agent = agent` or `booking.user` is linked to the agent via `customer_profile.agents`).

**Example:**  
`GET /api/v1/org-resources/agent-dashboard/bookings/?customer_id=456`  
→ Same effect, but 456 is a `Customer.id` from the agent’s customer list; it is resolved to that customer’s `user_id` before filtering.

### Option B: Main booking list

**Endpoint:** `GET /api/v1/booking/` (or the app’s main booking list URL).

**Query parameters for agents:**

| Param     | Type | Description |
|-----------|------|-------------|
| `user_id` | int  | Restrict to bookings for this User id. For agents, results are still limited to bookings where `agent = agent` or `user` is linked to the agent via `user__customer_profile__agents`. |

Agents see only their own bookings and those of customers linked to them; passing `user_id` further narrows the list to that customer’s bookings.

**Example:**  
`GET /api/v1/booking/?user_id=123`  
→ For an agent, only bookings for User id 123 that the agent is allowed to see.

### Who counts as “this agent’s customer”

- `booking.agent = current_agent`, or  
- `booking.user` has a `Customer` profile with `agents` containing the current agent (e.g. created/linked via `ensure_agent_contact_linked_as_customer` when using guest_* fields on pre-confirm).

Use **user_id** when you have the User id (e.g. from login or from the customer’s `user.id`). Use **customer_id** on the dashboard when you only have the Customer id from `/api/v1/org-resources/agent-dashboard/customers/`.
