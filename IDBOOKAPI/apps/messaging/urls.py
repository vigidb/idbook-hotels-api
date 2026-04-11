from rest_framework import routers

from apps.messaging.viewsets import (
    ContactViewSet,
    ContactUploadSessionViewSet,
    CampaignViewSet,
    CampaignStepViewSet,
    MessageLogViewSet,
    SmsTemplateViewSet,
    EmailTemplateViewSet,
    MessagingProviderConfigViewSet,
    TemplateVariablesViewSet,
    MessagingTestViewSet,
)

router = routers.DefaultRouter()
router.register(r"contacts", ContactViewSet, basename="messaging-contacts")
router.register(r"contact-uploads", ContactUploadSessionViewSet, basename="messaging-contact-uploads")
router.register(r"campaigns", CampaignViewSet, basename="messaging-campaigns")
router.register(r"campaign-steps", CampaignStepViewSet, basename="messaging-campaign-steps")
router.register(r"message-logs", MessageLogViewSet, basename="messaging-message-logs")
router.register(r"email-templates", EmailTemplateViewSet, basename="messaging-email-templates")
router.register(
    r"sms-templates",
    SmsTemplateViewSet,
    basename="messaging-sms-templates",
)
router.register(
    r"provider-configs",
    MessagingProviderConfigViewSet,
    basename="messaging-provider-configs",
)
router.register(r"template-variables", TemplateVariablesViewSet, basename="messaging-template-variables")
router.register(r"tests", MessagingTestViewSet, basename="messaging-tests")

urlpatterns = []

