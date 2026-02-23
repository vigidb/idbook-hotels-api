"""
Utility functions for linking customers to agents automatically.
"""
from django.db.models import Q
from apps.customer.models import Customer
from apps.org_resources.models import AgentDetail

# Group name used when creating Customer records for agent's end-customers
AGENT_CUSTOMER_GROUP_NAME = "AGENT-CUST"


def get_or_create_end_customer_user_for_agent(contact_email, contact_phone, contact_name, agent_user):
    """
    When an agent books on behalf of someone else with different contact details,
    resolve or create the end-customer user. Use this to set booking.user so
    link_customer_to_agent_on_booking links the correct customer to the agent.

    - If contact matches agent's email/mobile, returns agent_user.
    - If existing user found by contact_email or contact_phone, returns that user.
    - If no user and contact_email provided, creates User (B2C-GRP/B2C-GUEST),
      does NOT create Customer — link_customer_to_agent_on_booking will create
      Customer with group_name=AGENT_CUSTOMER_GROUP_NAME.

    Returns:
        User instance to use as booking.user
    """
    if not agent_user:
        return None
    contact_email = (contact_email or "").strip().lower()
    contact_phone = (contact_phone or "").strip()
    agent_email = (getattr(agent_user, "email", None) or "").strip().lower()
    agent_mobile = (getattr(agent_user, "mobile_number", None) or "").strip()
    if (not contact_email and not contact_phone) or (
        contact_email == agent_email and (not contact_phone or contact_phone == agent_mobile)
    ):
        return agent_user

    from apps.authentication.models import User
    from apps.authentication.utils.db_utils import get_user_from_email
    from apps.authentication.utils.authentication_utils import add_group_for_guest_user

    existing = None
    if contact_email:
        existing = get_user_from_email(contact_email)
    if not existing and contact_phone:
        existing = User.objects.filter(mobile_number=contact_phone).first()
    if existing:
        return existing

    if not contact_email:
        return agent_user

    user_details = {
        "email": contact_email,
        "mobile_number": contact_phone or "",
        "name": contact_name or "",
        "email_verified": False,
        "mobile_verified": False,
    }
    user = User.objects.create(**user_details)
    user = add_group_for_guest_user(user)
    return user


def link_user_to_agent_as_customer(user, agent):
    """
    Link a user to an agent as customer (AGENT-CUST). Used when agent books
    for someone else with different contact — we create/link that contact
    for CRM without changing booking.user (booking.user stays agent for wallet).
    """
    if not user or not agent:
        return
    customer = Customer.objects.filter(user=user).first()
    if customer:
        customer.agents.add(agent)
        customer.primary_agent = agent
        customer.save()
    else:
        from apps.customer.utils.db_utils import create_customer_signup_entry
        customer = create_customer_signup_entry(
            user=user,
            added_user=agent.added_user if agent.added_user else None,
            group_name=AGENT_CUSTOMER_GROUP_NAME,
        )
        if customer:
            customer.agents.add(agent)
            customer.primary_agent = agent
            customer.save()


def ensure_agent_contact_linked_as_customer(agent_detail, contact_email, contact_phone, contact_name):
    """
    When agent books with different contact details, ensure that contact is
    created/linked as agent's customer (AGENT-CUST) for CRM. Does not change
    booking.user — booking remains on agent so wallet deduction uses agent.
    """
    if not agent_detail:
        return
    agent_user = getattr(agent_detail, "added_user", None)
    if not agent_user:
        return
    contact_email = (contact_email or "").strip().lower()
    contact_phone = (contact_phone or "").strip()
    agent_email = (getattr(agent_user, "email", None) or "").strip().lower()
    agent_mobile = (getattr(agent_user, "mobile_number", None) or "").strip()
    if (not contact_email and not contact_phone) or (
        contact_email == agent_email and (not contact_phone or contact_phone == agent_mobile)
    ):
        return
    end_user = get_or_create_end_customer_user_for_agent(
        contact_email=contact_email,
        contact_phone=contact_phone,
        contact_name=contact_name or "",
        agent_user=agent_user,
    )
    if end_user and end_user != agent_user:
        link_user_to_agent_as_customer(end_user, agent_detail)


def link_customer_to_agent_on_booking(booking, agent):
    """
    Automatically link customer to agent when agent creates booking.
    - If customer doesn't have this agent, add to ManyToMany
    - Update primary_agent to this agent (most recent)
    - Handle existing customers gracefully
    - New customers created for agent bookings use group_name AGENT-CUST
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
        # Customer doesn't exist yet, create it with AGENT-CUST group
        from apps.customer.utils.db_utils import create_customer_signup_entry

        customer = create_customer_signup_entry(
            user=booking.user,
            added_user=agent.added_user if agent.added_user else None,
            group_name=AGENT_CUSTOMER_GROUP_NAME,
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
