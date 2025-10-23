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
        
        # Send email confirmation
        email_data = {
            'template_name': 'flight_booking_confirmation',
            'subject': f'Flight Booking Confirmed - {booking.confirmation_code}',
            'recipient_email': notification_data.get('email', booking.user.email),
            'context': {
                'booking': booking,
                'flight_details': notification_data.get('flight_details', {}),
                'passengers': notification_data.get('passengers', []),
                'payment_info': notification_data.get('payment_info', {})
            }
        }
        
        send_booking_email_task.delay(email_data)
        
        # Send SMS confirmation if phone number available
        if notification_data.get('phone') or booking.user.mobile_number:
            sms_data = {
                'phone': notification_data.get('phone', booking.user.mobile_number),
                'message': f'Your flight booking {booking.confirmation_code} is confirmed. Check email for details.',
                'template_name': 'flight_booking_sms'
            }
            send_booking_sms_task.delay(sms_data)
        
        logger.info(f"Flight booking confirmation notifications sent for booking {booking_id}")
        
        return {
            'success': True,
            'message': f'Confirmation notifications sent for booking {booking_id}',
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
        
        # Determine notification type based on status update
        notification_type = 'flight_status_update'
        if 'delay' in status_update:
            notification_type = 'flight_delay'
        elif 'gate_change' in status_update:
            notification_type = 'gate_change'
        elif 'cancellation' in status_update:
            notification_type = 'flight_cancellation'
        
        # Send email notification
        email_data = {
            'template_name': notification_type,
            'subject': f'Flight Status Update - {booking.confirmation_code}',
            'recipient_email': booking.user.email,
            'context': {
                'booking': booking,
                'status_update': status_update,
                'flight_details': booking.flight_booking
            }
        }
        
        send_booking_email_task.delay(email_data)
        
        # Send SMS for important updates
        if notification_type in ['flight_delay', 'gate_change', 'flight_cancellation']:
            sms_message = f"Flight {booking.confirmation_code}: {status_update.get('message', 'Status updated')}. Check email for details."
            
            sms_data = {
                'phone': booking.user.mobile_number,
                'message': sms_message,
                'template_name': notification_type
            }
            send_booking_sms_task.delay(sms_data)
        
        logger.info(f"Flight status update notifications sent for booking {booking_id}: {notification_type}")
        
        return {
            'success': True,
            'message': f'Status update notifications sent for booking {booking_id}',
            'notification_type': notification_type,
            'booking_id': booking_id
        }
        
    except Exception as e:
        logger.error(f"Failed to send flight status update for booking {booking_id}: {str(e)}")
        return {
            'success': False,
            'message': f'Failed to send status update: {str(e)}',
            'error': str(e)
        }