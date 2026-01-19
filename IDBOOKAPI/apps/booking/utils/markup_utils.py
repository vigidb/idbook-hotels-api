"""
Utility functions for calculating and applying agent markup to bookings.
"""
from decimal import Decimal
from apps.org_resources.models import AgentDetail, AgentMarkupConfig


class AgentMarkupCalculator:
    """Calculate agent markup for bookings"""
    
    @staticmethod
    def get_agent_markup(agent_id, base_amount, markup_override=None):
        """
        Get agent markup configuration and calculate markup amount.
        
        Args:
            agent_id: ID of the agent
            base_amount: Base booking amount before markup
            markup_override: Optional dict with 'percent' or 'amount' to override default
            
        Returns:
            dict with:
                - markup_percent: Percentage used (if percentage type)
                - markup_amount: Calculated markup amount
                - final_price: Base amount + markup
                - markup_type: 'PERCENT' or 'FIXED'
        """
        try:
            agent = AgentDetail.objects.get(id=agent_id)
        except AgentDetail.DoesNotExist:
            return {
                'markup_percent': None,
                'markup_amount': Decimal('0.00'),
                'final_price': Decimal(str(base_amount)),
                'markup_type': None
            }
        
        # Get agent markup config
        try:
            markup_config = agent.markup_config
        except AgentMarkupConfig.DoesNotExist:
            # No markup config, return base amount
            return {
                'markup_percent': None,
                'markup_amount': Decimal('0.00'),
                'final_price': Decimal(str(base_amount)),
                'markup_type': None
            }
        
        # Check if markup is active
        if not markup_config.is_active:
            return {
                'markup_percent': None,
                'markup_amount': Decimal('0.00'),
                'final_price': Decimal(str(base_amount)),
                'markup_type': None
            }
        
        # Use override if provided, otherwise use default
        if markup_override:
            if 'percent' in markup_override:
                markup_type = 'PERCENT'
                markup_value = Decimal(str(markup_override['percent']))
                markup_amount = (base_amount * markup_value) / Decimal('100')
            elif 'amount' in markup_override:
                markup_type = 'FIXED'
                markup_value = Decimal(str(markup_override['amount']))
                markup_amount = markup_value
            else:
                markup_type = markup_config.markup_type
                if markup_type == 'PERCENT':
                    markup_value = markup_config.default_markup_percent
                    markup_amount = (base_amount * markup_value) / Decimal('100')
                else:
                    markup_value = markup_config.default_markup_amount or Decimal('0.00')
                    markup_amount = markup_value
        else:
            # Use default from config
            markup_type = markup_config.markup_type
            if markup_type == 'PERCENT':
                markup_value = markup_config.default_markup_percent
                markup_amount = (base_amount * markup_value) / Decimal('100')
            else:
                markup_value = markup_config.default_markup_amount or Decimal('0.00')
                markup_amount = markup_value
        
        final_price = Decimal(str(base_amount)) + markup_amount
        
        return {
            'markup_percent': float(markup_value) if markup_type == 'PERCENT' else None,
            'markup_amount': markup_amount,
            'final_price': final_price,
            'markup_type': markup_type
        }
    
    @staticmethod
    def apply_markup_to_booking(booking, agent_id, markup_override=None):
        """
        Apply markup to a booking instance.
        
        Args:
            booking: Booking instance
            agent_id: ID of the agent
            markup_override: Optional dict to override default markup
            
        Returns:
            Updated booking instance (not saved)
        """
        # Use final_amount as base for markup calculation
        base_amount = booking.final_amount or booking.subtotal or Decimal('0.00')
        
        markup_calc = AgentMarkupCalculator.get_agent_markup(
            agent_id, base_amount, markup_override
        )
        
        # Update booking with markup details
        if markup_calc['markup_percent'] is not None:
            booking.agent_markup_percent = Decimal(str(markup_calc['markup_percent']))
        booking.agent_markup_amount = markup_calc['markup_amount']
        booking.final_price_with_markup = markup_calc['final_price']
        
        return booking
