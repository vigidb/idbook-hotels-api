from django.shortcuts import render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny


@method_decorator(csrf_exempt, name='dispatch')
class RazorpayPaymentPageView(APIView):
    """
    View to render Razorpay payment test page
    """
    permission_classes = [AllowAny]
    
    def get(self, request):
        """
        Render payment page with optional order_id, razorpay_key, amount, etc.
        """
        order_id = request.GET.get('order_id', '').strip()
        razorpay_key = request.GET.get('razorpay_key', getattr(settings, 'RAZORPAY_KEY_ID', '')).strip()
        amount = request.GET.get('amount', '').strip()
        name = request.GET.get('name', '').strip()
        email = request.GET.get('email', '').strip()
        contact = request.GET.get('contact', '').strip()
        
        context = {
            'order_id': order_id,
            'razorpay_key': razorpay_key,
            'amount': amount,
            'name': name,
            'email': email,
            'contact': contact,
        }
        
        # If order_id is provided, try to get order details
        if order_id:
            try:
                from apps.payment_gateways.mixins.razorpay_mixins import RazorpayMixin
                razorpay_mixin = RazorpayMixin()
                order_result = razorpay_mixin.get_order_details(order_id)
                
                if order_result.get('success'):
                    order_data = order_result['order']
                    context['order_details'] = {
                        'order_id': order_id,
                        'amount': float(order_data.get('amount', 0)) / 100,  # Convert from paise to rupees
                        'currency': order_data.get('currency', 'INR'),
                    }
                    # Auto-fill amount if not provided
                    if not amount:
                        context['amount'] = str(order_data.get('amount', ''))
            except Exception as e:
                # If order fetch fails, just continue without order details
                pass
        
        return render(request, 'razorpay_payment.html', context)

