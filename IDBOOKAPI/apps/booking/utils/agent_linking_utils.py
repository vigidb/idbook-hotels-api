"""
Utility functions for linking customers to agents automatically.
"""
from django.db.models import Q
from apps.customer.models import Customer
from apps.org_resources.models import AgentDetail


def link_customer_to_agent_on_booking(booking, agent):
    """
    Automatically link customer to agent when agent creates booking.
    - If customer doesn't have this agent, add to ManyToMany
    - Update primary_agent to this agent (most recent)
    - Handle existing customers gracefully
    """
    if not booking.user or not agent:
        return
    
    customer = Customer.objects.filter(user=booking.user).first()
    if customer:
        # Add agent to customer's agents (ManyToMany)
        customer.agents.add(agent)
        # Update primary agent to most recent
        customer.primary_agent = agent
        customer.save()
    else:
        # Customer doesn't exist yet, create it
        from apps.customer.utils.db_utils import create_customer_signup_entry
        customer = create_customer_signup_entry(
            user=booking.user,
            added_user=agent.added_user if agent.added_user else None,
            group_name="DEFAULT"
        )
        if customer:
            # Add agent to customer's agents (ManyToMany)
            customer.agents.add(agent)
            # Set as primary agent
            customer.primary_agent = agent
            customer.save()


def handle_direct_booking_customer_link(booking):
    """
    When customer books directly, maintain last agent relationship.
    - Keep primary_agent if exists
    - Mark booking_source as 'DIRECT'
    """
    if not booking.user:
        return
    
    customer = Customer.objects.filter(user=booking.user).first()
    if customer and customer.primary_agent:
        # Keep primary_agent relationship
        # Booking source already set to 'DIRECT' by default
        pass


def get_agent_for_user(user):
    """
    Get AgentDetail for user if user is an agent.
    
    Args:
        user: User instance
        
    Returns:
        AgentDetail instance or None
    """
    if not user:
        return None
    
    try:
        # Check if user is linked to an AgentDetail
        agent_detail = AgentDetail.objects.filter(
            Q(added_user=user) | 
            Q(contact_email_address=user.email)
        ).first()
        return agent_detail
    except Exception:
        return None
