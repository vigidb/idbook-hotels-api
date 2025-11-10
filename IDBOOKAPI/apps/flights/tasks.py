"""
Celery tasks for AirIQ token management and flight operations
"""

import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from .services.airiq_service import AirIQService

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def refresh_airiq_token_task(self):
    """
    Daily refresh of AirIQ authentication token
    This task should be scheduled to run every morning
    """
    try:
        logger.info("Starting AirIQ token refresh task")
        
        airiq_service = AirIQService()
        success = airiq_service.refresh_token_if_needed()
        
        if success:
            # Get token status for logging
            status = AirIQService.get_token_status()
            logger.info(f"AirIQ token refresh successful: {status}")
            return {
                'success': True,
                'message': 'AirIQ token refreshed successfully',
                'token_status': status
            }
        else:
            logger.error("AirIQ token refresh failed")
            return {
                'success': False,
                'message': 'AirIQ token refresh failed',
                'token_status': AirIQService.get_token_status()
            }
            
    except Exception as e:
        logger.error(f"AirIQ token refresh task failed: {str(e)}")
        
        # Retry with exponential backoff
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries * 60  # 1min, 2min, 4min
            logger.info(f"Retrying AirIQ token refresh in {countdown} seconds")
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            'success': False,
            'message': f'AirIQ token refresh failed after {self.max_retries} retries: {str(e)}',
            'error': str(e)
        }


@shared_task
def cleanup_expired_airiq_tokens_task():
    """
    Clean up expired AirIQ tokens from database
    This task should be scheduled to run daily
    """
    try:
        logger.info("Starting AirIQ token cleanup task")
        
        expired_count = AirIQService.cleanup_expired_tokens()
        
        logger.info(f"AirIQ token cleanup completed. Deactivated {expired_count} expired tokens")
        
        return {
            'success': True,
            'message': f'Cleaned up {expired_count} expired tokens',
            'expired_count': expired_count
        }
        
    except Exception as e:
        logger.error(f"AirIQ token cleanup task failed: {str(e)}")
        return {
            'success': False,
            'message': f'Token cleanup failed: {str(e)}',
            'error': str(e)
        }


@shared_task
def check_airiq_token_status_task():
    """
    Check and report AirIQ token status for monitoring
    This task can be run hourly for monitoring purposes
    """
    try:
        status = AirIQService.get_token_status()
        
        logger.info(f"AirIQ token status check: {status}")
        
        # Alert if token needs refresh
        if status.get('needs_refresh'):
            logger.warning("AirIQ token needs refresh - triggering refresh task")
            refresh_airiq_token_task.delay()
        
        return {
            'success': True,
            'token_status': status,
            'timestamp': timezone.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"AirIQ token status check failed: {str(e)}")
        return {
            'success': False,
            'message': f'Token status check failed: {str(e)}',
            'error': str(e)
        }


@shared_task(bind=True, max_retries=2)
def emergency_airiq_token_refresh_task(self):
    """
    Emergency token refresh when normal refresh fails
    This can be triggered manually or by monitoring systems
    """
    try:
        logger.warning("Starting emergency AirIQ token refresh")
        
        airiq_service = AirIQService()
        
        # Force new authentication regardless of current token status
        success = airiq_service.authenticate()
        
        if success:
            status = AirIQService.get_token_status()
            logger.info(f"Emergency AirIQ token refresh successful: {status}")
            return {
                'success': True,
                'message': 'Emergency AirIQ token refresh successful',
                'token_status': status
            }
        else:
            logger.error("Emergency AirIQ token refresh failed")
            return {
                'success': False,
                'message': 'Emergency AirIQ token refresh failed'
            }
            
    except Exception as e:
        logger.error(f"Emergency AirIQ token refresh task failed: {str(e)}")
        
        # Limited retries for emergency refresh
        if self.request.retries < self.max_retries:
            countdown = 30  # Retry in 30 seconds for emergency
            logger.warning(f"Retrying emergency AirIQ token refresh in {countdown} seconds")
            raise self.retry(countdown=countdown, exc=e)
        
        return {
            'success': False,
            'message': f'Emergency AirIQ token refresh failed after {self.max_retries} retries: {str(e)}',
            'error': str(e)
        }


@shared_task
def send_flight_booking_confirmation_task(booking_id: int, notification_data: dict):
    """
    Send flight booking confirmation notifications
    """
    try:
        from apps.booking.models import Booking
        from apps.booking.tasks import send_booking_email_task, send_booking_sms_task
        
        booking = Booking.objects.select_related('flight_booking', 'user').get(
            id=booking_id, 
            booking_type='FLIGHT'
        )
        
        # Use existing booking task signatures correctly
        # 1) Email confirmation with attached ticket (if any)
        send_booking_email_task.delay(booking_id, 'confirmed-booking')
        
        # 2) SMS confirmation using existing templates/notification integrations
        send_booking_sms_task.delay('FLIGHT_BOOKING_CONFIRMATION', {'booking_id': booking_id})
        
        logger.info(f"Flight booking confirmation notifications queued for booking {booking_id}")
        
        return {
            'success': True,
            'message': f'Confirmation notifications queued for booking {booking_id}',
            'booking_id': booking_id
        }
        
    except Exception as e:
        logger.error(f"Failed to send flight booking confirmation for booking {booking_id}: {str(e)}")
        return {
            'success': False,
            'message': f'Failed to send confirmation: {str(e)}',
            'error': str(e)
        }


@shared_task
def send_flight_status_update_task(booking_id: int, status_update: dict):
    """
    Send flight status update notifications to customers
    """
    try:
        from apps.booking.models import Booking
        from apps.booking.tasks import send_booking_email_task, send_booking_sms_task
        
        booking = Booking.objects.select_related('flight_booking', 'user').get(
            id=booking_id,
            booking_type='FLIGHT'
        )
        
        # Determine SMS notification type mapping supported by send_booking_sms_task
        sms_type = None
        if status_update.get('cancellation'):
            sms_type = 'FLIGHT_BOOKING_CANCEL'
        # For other updates (delay/gate change), reuse EMAIL only for now
        
        # Always send an email via the generic booking email task for status update templates
        # Note: booking.tasks doesn't have a generic template switch here, so keep using confirmed-booking email
        # or extend booking.tasks if specific email templates are needed.
        send_booking_email_task.delay(booking_id, 'confirmed-booking')
        
        if sms_type:
            params = {'booking_id': booking_id}
            if sms_type == 'FLIGHT_BOOKING_CANCEL':
                params['refund_amount'] = status_update.get('refund_amount', 0)
            send_booking_sms_task.delay(sms_type, params)
        
        logger.info(f"Flight status update notifications queued for booking {booking_id}")
        
        return {
            'success': True,
            'message': f'Status update notifications queued for booking {booking_id}',
            'booking_id': booking_id
        }
        
    except Exception as e:
        logger.error(f"Failed to send flight status update for booking {booking_id}: {str(e)}")
        return {
            'success': False,
            'message': f'Failed to send status update: {str(e)}',
            'error': str(e)
        }
