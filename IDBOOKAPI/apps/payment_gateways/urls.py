from django.urls import path
from apps.payment_gateways.views import UnifiedRazorpayWebhookView

urlpatterns = [
    path("razorpay/webhook/", UnifiedRazorpayWebhookView.as_view(), name="unified-razorpay-webhook"),
]

