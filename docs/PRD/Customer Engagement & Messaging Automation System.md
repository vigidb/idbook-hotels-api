**Messaging Automation & Campaign System** inside our existing OTA platform (Idbook).

The goal is:

* **Automated SMS / Email / WhatsApp campaigns**
* **Event-based travel automation**
* **Segmentation**
* **Full configuration from admin**
* **Minimal manual work**

---

# 1. Product Overview

## Feature Name

**Customer Engagement & Messaging Automation System**

## Objective

Enable the platform to:

1. Send **bulk SMS / Email campaigns**
2. Trigger **automated messages based on user behaviour**
3. Segment users by **groups, activity, and travel interest**
4. Track **campaign performance**
5. Configure everything via **admin panel**

---

# 2. Key Integrations

Messaging providers:

* MSG91 for SMS
* Amazon Simple Email Service for email
* Gupshup for WhatsApp

---

# 3. User Groups to Support

Your system already supports groups.

Messaging system must allow targeting:

```text
Guest
B2C User
Corporate User
Agent
Hotelier
Business Staff
```

Also allow targeting by:

```text
City
Country
Booking history
Search behaviour
Travel interest
```

---

# 4. System Architecture

```
User Events
    ↓
Event Store
    ↓
Automation Engine
    ↓
Campaign Manager
    ↓
Messaging Queue
    ↓
SMS / Email / WhatsApp
```

Key services:

```
Contact Service
Campaign Service
Automation Engine
Message Queue
Analytics Service
```

---

# 5. Database Design

## Contact Model

```python
Contact
--------
id
user_id (optional)
name
phone
email
city
country
group_type
opt_out_sms
opt_out_email
opt_out_whatsapp
is_blacklisted
source
created_at
```

---

## Campaign Model

```python
Campaign
--------
id
name
channel (sms/email/whatsapp)
message_template
email_subject
status (draft/scheduled/running/completed)
target_group
target_filters
schedule_time
created_by
created_at
```

---

## Campaign Contacts

```python
CampaignContact
---------------
campaign
contact
status
sent_at
response
```

---

## Automation Rules

```python
AutomationRule
--------------
id
name
trigger_event
conditions
delay
channel
template
status
```

---

## Message Logs

```python
MessageLog
----------
contact
campaign
channel
status
provider_response
sent_at
```

---

# 6. Admin Panel Features (React)

Admin UI sections:

### Campaigns

```
Create campaign
Select channel
Select target group
Upload contacts
Preview message
Schedule send
View analytics
```

---

### Automations

```
Create automation rule
Select trigger event
Add conditions
Choose template
Configure delay
Enable/disable rule
```

---

### Contacts

```
Import contacts
Edit contacts
Blacklist contacts
View engagement history
```

---

### Templates

```
SMS templates
Email templates
WhatsApp templates
Variables support
```

---

# 7. Core Events to Track

These events power automation.

```text
user_registered
hotel_search
hotel_view
package_view
booking_started
booking_abandoned
booking_completed
corporate_lead_created
agent_registered
```

---

# 8. Personalization Variables

Templates should support:

```
{name}
{city}
{destination}
{hotel_name}
{price}
{booking_link}
```

---

# 9. Edge Case Handling

System must handle:

### Data issues

```
duplicate contacts
invalid phone numbers
invalid emails
```

### Messaging issues

```
SMS provider failure
email bounce
template mismatch
```

### Compliance

```
opt-out
unsubscribe
DLT template rules
```

### Operational

```
campaign pause
rate limiting
retry mechanism
```

---

# 10. Metrics Dashboard

Campaign analytics:

```
messages sent
delivery rate
open rate
click rate
conversion rate
revenue generated
```

---

# 11. Development Plan (Single Developer)

Below is **realistic execution order**.

---

# Day 1–3 (MVP Messaging Engine)

Goal: **Send campaigns**

Tasks:

### Backend

Create models:

```
Contact
Campaign
CampaignContact
MessageLog
```

APIs:

```
POST /contacts/upload
POST /campaign/create
POST /campaign/send
GET /campaign/status
```

Implement:

```
CSV upload
contact validation
deduplication
```

Integrate SMS:

```
MSG91 API
```

Integrate Email:

```
Amazon SES
```

---

### Admin UI

React pages:

```
Contact upload
Campaign creation
Campaign list
Campaign send button
```

---

# Day 4–7 (Automation System)

Goal: **Trigger messages automatically**

Backend:

Create:

```
Event model
AutomationRule model
```

Create event tracking API:

```
POST /events
```

Implement automation worker:

```
trigger rule
schedule message
```

Example automation:

```
hotel_search
→ send deal SMS
```

---

# Day 8–14 (Advanced Campaign Features)

Add:

### Segmentation

Filter contacts by:

```
group
city
booking count
last activity
```

Add:

```
campaign scheduling
batch sending
rate limiting
retry logic
```

Add unsubscribe system.

---

# Day 15–21 (Analytics & Optimization)

Implement:

```
click tracking
open tracking
campaign analytics
```

Add dashboard:

```
conversion stats
ROI stats
```

---

# Day 22–30 (Growth Features)

Add high ROI features.

### Price Drop Alerts

Trigger when:

```
hotel price decreases
```

Send message to users who viewed.

---

### Booking Abandonment

Detect:

```
booking started
but not completed
```

Send reminder.

---

### Travel Intent Engine

Detect:

```
destination search
package view
```

Send personalized deals.

---

# 12. Security & Permissions

Only specific groups should access admin.

Example:

```
Business staff
Marketing team
Admin
```

Permission roles:

```
campaign_manager
automation_manager
analytics_viewer
```

---

# 13. Configuration System

Everything should be configurable.

Example config model:

```python
SystemConfig
------------
key
value
description
```

Examples:

```
sms_rate_limit
max_campaign_size
allowed_sending_time
retry_attempts
```

---

# 14. Expected Impact

After implementation:

```
5–12% traffic conversion
automated lead recovery
higher repeat bookings
```

---

# 15. Future Enhancements

Later improvements:

```
AI campaign generation
travel recommendation engine
dynamic pricing alerts
WhatsApp chatbot booking
```
