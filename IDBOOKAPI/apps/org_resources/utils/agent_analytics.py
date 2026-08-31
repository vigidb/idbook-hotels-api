"""
Utility functions for agent dashboard analytics and statistics.
"""
from django.db.models import Count, Sum, Avg, Q, Max
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from apps.booking.models import Booking
from apps.customer.models import Customer
from apps.org_resources.models import AgentDetail


def get_agent_booking_stats(agent_id, date_range=None):
    """
    Get booking statistics for an agent.
    
    Args:
        agent_id: ID of the AgentDetail
        date_range: Optional tuple of (start_date, end_date)
        
    Returns:
        dict with booking statistics
    """
    try:
        agent = AgentDetail.objects.filter(id=agent_id).first()
        if not agent:
            return {}
        
        # Base queryset for agent bookings
        bookings_query = Booking.objects.filter(
            Q(agent=agent) | Q(user__customer_profile__agents=agent)
        )
        
        if date_range:
            start_date, end_date = date_range
            bookings_query = bookings_query.filter(
                created__date__gte=start_date,
                created__date__lte=end_date
            )
        
        stats = bookings_query.aggregate(
            total_bookings=Count('id'),
            confirmed_bookings=Count('id', filter=Q(status='confirmed')),
            pending_bookings=Count('id', filter=Q(status='pending')),
            cancelled_bookings=Count('id', filter=Q(status='canceled')),
            completed_bookings=Count('id', filter=Q(status='completed')),
            total_revenue=Sum('final_amount'),
            avg_booking_value=Avg('final_amount'),
            agent_bookings=Count('id', filter=Q(agent=agent)),
            direct_bookings=Count('id', filter=Q(booking_source='DIRECT')),
        )
        
        return {
            'total_bookings': stats['total_bookings'] or 0,
            'confirmed_bookings': stats['confirmed_bookings'] or 0,
            'pending_bookings': stats['pending_bookings'] or 0,
            'cancelled_bookings': stats['cancelled_bookings'] or 0,
            'completed_bookings': stats['completed_bookings'] or 0,
            'total_revenue': float(stats['total_revenue'] or 0),
            'avg_booking_value': float(stats['avg_booking_value'] or 0),
            'agent_bookings': stats['agent_bookings'] or 0,
            'direct_bookings': stats['direct_bookings'] or 0,
        }
    except Exception as e:
        print(f"Error getting agent booking stats: {str(e)}")
        return {}


def get_agent_revenue(agent_id, date_range=None):
    """
    Get revenue statistics for an agent.
    
    Args:
        agent_id: ID of the AgentDetail
        date_range: Optional tuple of (start_date, end_date)
        
    Returns:
        dict with revenue statistics
    """
    try:
        agent = AgentDetail.objects.filter(id=agent_id).first()
        if not agent:
            return {}
        
        bookings_query = Booking.objects.filter(
            Q(agent=agent) | Q(user__customer_profile__agents=agent)
        ).filter(status__in=['confirmed', 'completed'])
        
        if date_range:
            start_date, end_date = date_range
            bookings_query = bookings_query.filter(
                created__date__gte=start_date,
                created__date__lte=end_date
            )
        
        revenue_stats = bookings_query.aggregate(
            total_revenue=Sum('final_amount'),
            total_with_markup=Sum('final_price_with_markup'),
            total_markup=Sum('agent_markup_amount'),
            booking_count=Count('id')
        )
        
        return {
            'total_revenue': float(revenue_stats['total_revenue'] or 0),
            'total_with_markup': float(revenue_stats['total_with_markup'] or 0),
            'total_markup': float(revenue_stats['total_markup'] or 0),
            'booking_count': revenue_stats['booking_count'] or 0,
        }
    except Exception as e:
        print(f"Error getting agent revenue: {str(e)}")
        return {}


def get_agent_commission_summary(agent_id, date_range=None):
    """
    Get commission summary for an agent.
    
    Args:
        agent_id: ID of the AgentDetail
        date_range: Optional tuple of (start_date, end_date)
        
    Returns:
        dict with commission statistics
    """
    try:
        agent = AgentDetail.objects.filter(id=agent_id).first()
        if not agent:
            return {}
        
        bookings_query = Booking.objects.filter(
            Q(agent=agent) | Q(user__customer_profile__agents=agent)
        ).filter(status__in=['confirmed', 'completed'])
        
        if date_range:
            start_date, end_date = date_range
            bookings_query = bookings_query.filter(
                created__date__gte=start_date,
                created__date__lte=end_date
            )
        
        # Get bookings with commission info
        bookings_with_commission = bookings_query.filter(
            commission_info__isnull=False
        )
        
        commission_stats = bookings_with_commission.aggregate(
            total_commission=Sum('commission_info__com_amnt'),
            total_commission_with_tax=Sum('commission_info__com_amnt_withtax'),
            pending_payout=Count('id', filter=Q(commission_info__payout_status='PENDING')),
            paid_payout=Count('id', filter=Q(commission_info__payout_status='PAID')),
        )
        
        return {
            'total_commission': float(commission_stats['total_commission'] or 0),
            'total_commission_with_tax': float(commission_stats['total_commission_with_tax'] or 0),
            'pending_payout_count': commission_stats['pending_payout'] or 0,
            'paid_payout_count': commission_stats['paid_payout'] or 0,
        }
    except Exception as e:
        print(f"Error getting agent commission summary: {str(e)}")
        return {}


def get_agent_customer_count(agent_id):
    """
    Get customer count for an agent.
    
    Args:
        agent_id: ID of the AgentDetail
        
    Returns:
        int: Number of customers linked to agent
    """
    try:
        agent = AgentDetail.objects.filter(id=agent_id).first()
        if not agent:
            return 0
        
        return Customer.objects.filter(agents=agent).count()
    except Exception as e:
        print(f"Error getting agent customer count: {str(e)}")
        return 0


def get_agent_top_bookings(agent_id, limit=10, date_range=None):
    """
    Get top bookings for an agent by revenue.
    
    Args:
        agent_id: ID of the AgentDetail
        limit: Number of bookings to return
        date_range: Optional tuple of (start_date, end_date)
        
    Returns:
        list of booking dicts
    """
    try:
        agent = AgentDetail.objects.filter(id=agent_id).first()
        if not agent:
            return []
        
        bookings_query = Booking.objects.filter(
            Q(agent=agent) | Q(user__customer_profile__agents=agent)
        ).select_related('user', 'hotel_booking', 'flight_booking')
        
        if date_range:
            start_date, end_date = date_range
            bookings_query = bookings_query.filter(
                created__date__gte=start_date,
                created__date__lte=end_date
            )
        
        top_bookings = bookings_query.order_by('-final_amount')[:limit]
        
        return [
            {
                'id': booking.id,
                'reference_code': booking.reference_code,
                'booking_type': booking.booking_type,
                'final_amount': float(booking.final_amount),
                'status': booking.status,
                'created': booking.created.isoformat(),
                'booking_source': booking.booking_source,
            }
            for booking in top_bookings
        ]
    except Exception as e:
        print(f"Error getting agent top bookings: {str(e)}")
        return []


def get_agent_customer_stats(agent_id):
    """
    Get customer statistics for an agent.
    
    Args:
        agent_id: ID of the AgentDetail
        
    Returns:
        dict with customer statistics
    """
    try:
        agent = AgentDetail.objects.filter(id=agent_id).first()
        if not agent:
            return {}
        
        customers = Customer.objects.filter(agents=agent)
        
        # Get customers with bookings
        customers_with_bookings = customers.filter(
            user__booking_user__agent=agent
        ).distinct()
        
        # Get primary customers
        primary_customers = customers.filter(primary_agent=agent)
        
        return {
            'total_customers': customers.count(),
            'customers_with_bookings': customers_with_bookings.count(),
            'primary_customers': primary_customers.count(),
        }
    except Exception as e:
        print(f"Error getting agent customer stats: {str(e)}")
        return {}
