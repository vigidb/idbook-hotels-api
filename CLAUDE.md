# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

IDBOOK Hotels API is a Django REST Framework-based backend for a hotel booking platform that serves web, Android, and iOS clients. The system handles hotel listings, bookings, payments, customer management, and partner (hotelier) operations.

## Development Commands

### Initial Setup
```bash
# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux

# Install dependencies
cd IDBOOKAPI
pip install -r requirements.txt
```

### Running the Application

**Local Development:**
```bash
cd IDBOOKAPI
python manage.py runserver
# Server runs at http://localhost:8000
```

**Docker Development:**
```bash
cd IDBOOKAPI
docker-compose up
# Includes PostgreSQL database and Django web service
```

### Database Management

```bash
cd IDBOOKAPI

# Create migrations
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser
```

### Testing & Quality

```bash
cd IDBOOKAPI

# Run tests (uses pytest)
pytest

# Access admin interface
# Navigate to http://localhost:8000/admin/
```

### Celery (Background Tasks)

```bash
cd IDBOOKAPI

# Start Celery worker
celery -A IDBOOKAPI worker --loglevel=info

# Start Celery beat (scheduled tasks)
celery -A IDBOOKAPI beat --loglevel=info
```

### API Documentation

- Swagger UI: `http://localhost:8000/api/v1/docs2/`
- ReDoc: `http://localhost:8000/api/v1/docs/`

## Architecture

### Project Structure

```
IDBOOKAPI/
├── IDBOOKAPI/              # Core settings and configuration
│   ├── settings.py         # Django settings (environment-based)
│   ├── urls.py            # Main URL routing
│   ├── celery.py          # Celery configuration and task routing
│   ├── basic_resources.py # Shared constants and choices (room types, statuses, etc.)
│   ├── utils.py           # Common utility functions
│   ├── permissions.py     # Custom DRF permissions
│   └── email_utils.py     # Email sending utilities
├── apps/                   # Django applications
│   ├── authentication/    # User auth, JWT, OTP verification
│   ├── hotels/           # Hotel listings, rooms, amenities
│   ├── booking/          # Booking flow, invoices, payments
│   ├── customer/         # Customer profiles, wallets
│   ├── org_resources/    # Business/org resources, recurring payments
│   ├── org_managements/  # Organization management
│   ├── administrator/    # Admin operations
│   ├── coupons/         # Discount coupons
│   ├── holiday_package/ # Tour packages
│   ├── vehicle_management/ # Vehicle booking
│   ├── analytics/       # Analytics and reporting
│   ├── log_management/  # Activity logging
│   └── payment_gateways/ # Payment integrations
├── api/                  # API-related code
├── templates/            # Email and PDF templates
├── manage.py
├── requirements.txt
└── docker-compose.yml
```

### Key App Organization

Each Django app follows a consistent structure:
- `models.py` - Database models
- `serializers.py` - DRF serializers for API endpoints
- `viewsets.py` - API viewsets (main business logic)
- `urls.py` - URL routing and router configuration
- `tasks.py` - Celery async tasks (emails, SMS, background jobs)
- `admin.py` - Django admin configuration
- `subviews/` - Additional viewset modules when main viewset gets too large
- `utils/` - App-specific utility functions
- `mixins/` - Reusable viewset mixins

### Authentication & Authorization

- **Authentication Backend**: JWT using `djangorestframework-simplejwt`
- **Custom Auth**: Phone/password authentication via `apps.authentication.mobile_authentication.PhonePasswordAuthBackend`
- **User Model**: Custom user model at `apps.authentication.User` (AUTH_USER_MODEL)
- **Token Lifetime**: Access tokens expire in 12 hours, refresh tokens in 1 day
- **Permissions**: Custom permissions in `IDBOOKAPI/permissions.py`

### Environment Configuration

The application uses `django-environ` for configuration management. Settings are loaded from `.env` files in `IDBOOKAPI/IDBOOKAPI/`:
- `.env` - Local development
- `.env.production` - Production settings

Key environment variables:
- `DEBUG` - Debug mode
- `DATABASE_*` - PostgreSQL connection settings
- `SECRET_KEY` - Django secret key
- `AWS_*` - S3 storage for media files
- `CELERY_BROKER_URL` - Redis connection for Celery
- `IMAGEKIT_*` - ImageKit.io for image processing
- Payment gateway credentials (PhonePe, PayU)
- SMS gateway credentials (Fast2SMS)
- Email configuration

### Database

- **Engine**: PostgreSQL
- **Location**: Connection details in environment variables
- **Timezone**: Asia/Kolkata (TIME_ZONE setting)
- **Media Storage**: AWS S3 (configured via `storage_backend.py`)

### Background Tasks (Celery)

**Queue Configuration** (`IDBOOKAPI/celery.py`):
- Email/SMS tasks route to `email-send-queue` (production) or `dev-email-send-queue` (development)
- Recurring payment tasks route to `recpay-initiate-queue`

**Scheduled Tasks (Celery Beat)**:
- Recurring payment initiation: Every 1 minute
- Wallet expiry check: Every 30 minutes

**Task Locations**:
- `apps.authentication.tasks` - OTP, signup emails
- `apps.booking.tasks` - Booking confirmations, invoices, cancellations
- `apps.hotels.tasks` - Hotel notifications, service agreements
- `apps.org_resources.tasks` - Recurring payments, enquiries

### API Structure

**API Versioning**: All endpoints are versioned under `/api/v1/`

**Main API Endpoints**:
- `/api/v1/auth/token/` - JWT token obtain
- `/api/v1/auth/token/refresh/` - JWT token refresh
- `/api/v1/administrator/` - Admin operations
- `/api/v1/hotels/` - Hotel listings and management
- `/api/v1/booking/` - Booking operations
- `/api/v1/customer/` - Customer operations
- `/api/v1/org-resources/` - Organization resources
- `/api/v1/holiday-package/` - Tour packages
- `/api/v1/coupons/` - Coupon management
- `/api/v1/analytics/` - Analytics endpoints

### Important Constants & Choices

The file `IDBOOKAPI/IDBOOKAPI/basic_resources.py` contains all shared constants:
- `BOOKING_STATUS_CHOICES` - Booking statuses (pending, confirmed, canceled, completed, no_show, on_hold)
- `PAYMENT_TYPE` - Payment types (PAYMENT GATEWAY, WALLET, NBFC, DIRECT, BANK TRANSFER)
- `PAYMENT_MEDIUM` - Payment methods (PHONE PAY, PayU, Idbook, Hotel, etc.)
- `STATUS_CHOICES` - Invoice statuses (PI, Pending, Paid, Overdue, Refunded, etc.)
- Room types, bed types, property types, meal options
- Indian states and districts data
- All other domain-specific choices

### Key Business Logic Patterns

**Booking Flow**:
1. Customer searches hotels → `apps.hotels.viewsets`
2. Room availability checked → Hotel/Room models
3. Booking created → `apps.booking.viewsets`
4. Payment processed → `apps.booking.subviews.payment_viewset`
5. Confirmation sent via Celery → `apps.booking.tasks`
6. Invoice generated → `apps.booking.tasks.create_invoice_task`

**Wallet System**:
- Customers have wallet balances managed in `apps.customer`
- Transactions logged with types (credit/debit) via `TRANSACTION_FOR` choices
- Wallet expiry checked via scheduled Celery task

**Pro Membership**:
- Special rules for pro members in `apps.org_resources`
- Bonus and cashback system
- Recurring payment support

## Working with Migrations

When modifying models in `apps.*/models.py`:

```bash
cd IDBOOKAPI

# Generate migrations for specific app
python manage.py makemigrations app_name

# Generate migrations for all apps
python manage.py makemigrations

# View migration SQL without applying
python manage.py sqlmigrate app_name migration_name

# Apply migrations
python manage.py migrate
```

Note: Migration files are extensive (80+ migrations in some apps like hotels and booking). Review the existing migration patterns before creating new ones.

## Payment Gateway Integration

**PhonePe** (primary):
- Configuration in environment variables: `MERCHANT_ID`, `SALT_KEY`, `SALT_INDEX`, `PHONEPAY_URL`
- Payment flow in booking subviews

**PayU** (secondary):
- Configuration: `PAYU_KEY`, `PAYU_SALT`, `PAYU_URL`

Both gateways integrate via `apps.booking.subviews.payment_viewset`

## Common Development Workflows

### Adding a New API Endpoint

1. Define model in `apps/<app>/models.py` (if needed)
2. Create/update serializer in `apps/<app>/serializers.py`
3. Add viewset method or new viewset in `apps/<app>/viewsets.py`
4. Register route in `apps/<app>/urls.py`
5. Run migrations if model changed
6. Test via Swagger UI or API client

### Adding Background Tasks

1. Define task function in `apps/<app>/tasks.py` with `@shared_task` decorator
2. Register task route in `IDBOOKAPI/celery.py` `task_routes`
3. Call task using `.delay()` or `.apply_async()` from viewset
4. Test with running Celery worker

### Working with Invoices

Invoice-related code is in `apps.booking`:
- Models: `apps.booking.models` (Invoice, InvoiceItem, etc.)
- Migration script: `apps.booking.invoice_migration.py`
- Generation: `apps.booking.tasks.create_invoice_task`
- Status choices from `basic_resources.STATUS_CHOICES`

## Important Files to Review

- `IDBOOKAPI/IDBOOKAPI/basic_resources.py` - All domain constants and choices
- `IDBOOKAPI/IDBOOKAPI/utils.py` - Common utility functions used across apps
- `IDBOOKAPI/IDBOOKAPI/celery.py` - Task routing and scheduling
- `apps/booking/viewsets.py` - Core booking business logic (large file ~158KB)
- `apps/hotels/viewsets.py` - Hotel management logic (large file ~135KB)
- `apps/authentication/viewsets.py` - Auth flows and OTP (large file ~53KB)

## Debugging & Logs

Logging configuration is in `IDBOOKAPI/logger_dict.py` (imported in settings.py).

Access logs through:
- Django development server output
- Docker logs: `docker-compose logs -f`
- Application logs via `apps.log_management`

## Notes

- Media files are served from AWS S3 (MEDIA_URL points to S3 bucket)
- Static files are collected to `static/` directory
- CORS is enabled for all origins (CORS_ORIGIN_ALLOW_ALL = True)
- The codebase uses Django 4.2.3 and Python 3.11
- ImageKit.io is used for image upload and transformation
- SMS notifications use Fast2SMS gateway
