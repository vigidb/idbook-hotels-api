# AirIQ Token Management - Daily Refresh Implementation

## Overview
Implemented comprehensive daily token refresh system for AirIQ authentication to ensure continuous API access without hitting daily limits. The system automatically refreshes tokens when created yesterday and proactively manages token lifecycle.

## Key Features

### ✅ Daily Automatic Refresh
- **Daily Check**: Automatically detects if token was created yesterday
- **Proactive Refresh**: Refreshes tokens within 2 hours of expiry
- **Scheduled Tasks**: Celery beat schedules automatic daily refresh at 6:00 AM
- **Database Caching**: Uses `AirIQTokenCache` model to store tokens safely

### ✅ Enhanced AirIQ Service (`apps/flights/services/airiq_service.py`)

**New Methods Added:**
```python
def _should_refresh_token(self) -> bool
    # Checks if token needs daily refresh or proactive refresh

def refresh_token_if_needed(self) -> bool
    # Public method for scheduled token refresh

@classmethod
def cleanup_expired_tokens(cls)
    # Cleans up expired tokens from database

@classmethod  
def get_token_status(cls) -> dict
    # Returns comprehensive token status for monitoring
```

**Enhanced Logic:**
- Daily refresh detection based on creation date
- 2-hour proactive refresh window
- Improved error handling and logging
- Better token expiry management

### ✅ Celery Tasks (`apps/flights/tasks.py`)

**Token Management Tasks:**
1. **`refresh_airiq_token_task`**
   - Daily token refresh with retry logic
   - Exponential backoff: 1min, 2min, 4min retries
   - Comprehensive logging and status reporting

2. **`cleanup_expired_airiq_tokens_task`**
   - Daily cleanup of expired tokens
   - Database maintenance

3. **`check_airiq_token_status_task`**
   - Hourly token status monitoring
   - Automatic trigger of refresh if needed

4. **`emergency_airiq_token_refresh_task`**
   - Manual/emergency token refresh
   - For critical situations when normal refresh fails

**Flight Notification Tasks:**
5. **`send_flight_booking_confirmation_task`**
   - Comprehensive booking confirmation notifications
   - Email and SMS integration

6. **`send_flight_status_update_task`**
   - Flight status change notifications
   - Delay, gate change, cancellation alerts

### ✅ Scheduled Execution (Celery Beat)

**Daily Schedules:**
- **6:00 AM**: Daily token refresh (`refresh_airiq_token_task`)
- **2:00 AM**: Token cleanup (`cleanup_expired_airiq_tokens_task`)
- **Every Hour**: Status monitoring (`check_airiq_token_status_task`)

**Queue Management:**
- Dedicated `airiq-token-queue` (prod) / `dev-airiq-token-queue` (dev/test) for token management
- Separate from email/SMS queues for better performance

### ✅ Enhanced Token Cache Model

**Updated `AirIQTokenCache.cache_token()` method:**
```python
@classmethod
def cache_token(cls, token, expires_in_hours=24, expires_at=None):
    # Supports both relative hours and absolute datetime expiry
    # Better flexibility for token management
```

## Implementation Details

### Token Refresh Logic Flow

1. **Check Requirements**
   ```python
   # Check if token was created yesterday
   if token_created_date < current_date:
       return True  # Refresh needed
   
   # Check if expires within 2 hours  
   if expires_at <= now + timedelta(hours=2):
       return True  # Proactive refresh
   ```

2. **Authentication Process**
   ```python
   # Use cached token if valid and recent
   if not _should_refresh_token():
       use_cached_token()
   else:
       authenticate_with_airiq_api()
       cache_new_token()
   ```

3. **Error Handling**
   - Retry mechanism with exponential backoff
   - Fallback to emergency refresh
   - Comprehensive logging for debugging

### Monitoring & Alerting

**Token Status Information:**
```python
{
    'has_valid_token': True,
    'created_date': '2024-10-15',
    'expires_at': '2024-10-15T23:59:59',
    'hours_until_expiry': 8.5,
    'needs_refresh': False
}
```

**Automatic Alerts:**
- Logs warning when token needs refresh
- Triggers emergency refresh if normal refresh fails
- Status monitoring every hour

### Integration Points

**Flight Booking Integration:**
- Updated payment notifications to use new Celery tasks
- Enhanced booking confirmation with flight-specific data
- Status update notifications for flight changes

**Database Management:**
- Safe token storage with expiry tracking
- Automatic cleanup of expired records
- Transaction-safe token updates

## Usage Examples

### Manual Token Refresh
```python
from apps.flights.tasks import refresh_airiq_token_task

# Trigger manual refresh
result = refresh_airiq_token_task.delay()
```

### Check Token Status
```python
from apps.flights.services.airiq_service import AirIQService

status = AirIQService.get_token_status()
print(f"Token valid: {status['has_valid_token']}")
print(f"Expires in: {status['hours_until_expiry']} hours")
```

### Emergency Refresh
```python
from apps.flights.tasks import emergency_airiq_token_refresh_task

# For critical situations
result = emergency_airiq_token_refresh_task.delay()
```

## Production Deployment

### Required Environment Variables
- `AIRIQ_BASE_URL`: AirIQ API base URL
- `AIRIQ_AGENT_ID`: Agent ID for authentication
- `AIRIQ_USERNAME`: API username
- `AIRIQ_PASSWORD`: API password

### Celery Configuration
```bash
# Start Celery worker for token management
celery -A IDBOOKAPI worker -Q airiq-token-queue --loglevel=info
# Dev/test:
celery -A IDBOOKAPI worker -Q dev-airiq-token-queue --loglevel=info

# Start Celery beat for scheduled tasks
celery -A IDBOOKAPI beat --loglevel=info
```

### Monitoring Setup
- Monitor Celery task execution logs
- Set up alerts for token refresh failures  
- Track token expiry patterns
- Monitor API call success rates

## Benefits

### ✅ Reliability
- **No API Limit Issues**: Daily refresh prevents hitting limits
- **Proactive Management**: 2-hour buffer prevents expiry issues
- **Automatic Recovery**: Self-healing with retry mechanisms

### ✅ Operational Excellence
- **Zero Downtime**: Seamless token transitions
- **Comprehensive Logging**: Full audit trail
- **Monitoring Ready**: Status APIs for health checks

### ✅ Scalability
- **Queue-based**: Handles multiple concurrent requests
- **Database Cached**: Fast token access
- **Resource Efficient**: Minimal API calls

### ✅ Maintainability
- **Clear Separation**: Dedicated token management module
- **Configurable**: Easy to adjust schedules and timeouts
- **Testable**: Isolated components for unit testing

## Testing

### Unit Tests
```bash
# Test token refresh logic
python manage.py test apps.flights.tests.test_token_management

# Test Celery tasks
python manage.py test apps.flights.tests.test_tasks
```

### Manual Testing
```bash
# Check current token status
python manage.py shell
>>> from apps.flights.services.airiq_service import AirIQService
>>> AirIQService.get_token_status()

# Trigger manual refresh
>>> from apps.flights.tasks import refresh_airiq_token_task
>>> refresh_airiq_token_task.delay()
```

## Future Enhancements

### Planned Features
- **Multi-environment Support**: Different refresh schedules per environment
- **Token Pool Management**: Multiple tokens for high-volume operations
- **Advanced Monitoring**: Integration with monitoring tools (Prometheus, Grafana)
- **Auto-scaling**: Dynamic queue management based on load

The AirIQ token management system is now production-ready with comprehensive daily refresh, monitoring, and error handling capabilities!