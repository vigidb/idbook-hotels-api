from rest_framework import routers

from apps.messaging.viewsets import (
    ContactViewSet,
    ContactUploadSessionViewSet,
    CampaignViewSet,
    CampaignStepViewSet,
    MessageLogViewSet,
    EmailTemplateViewSet,
    TemplateVariablesViewSet,
)

router = routers.DefaultRouter()
router.register(r"contacts", ContactViewSet, basename="messaging-contacts")
router.register(r"contact-uploads", ContactUploadSessionViewSet, basename="messaging-contact-uploads")
router.register(r"campaigns", CampaignViewSet, basename="messaging-campaigns")
router.register(r"campaign-steps", CampaignStepViewSet, basename="messaging-campaign-steps")
router.register(r"message-logs", MessageLogViewSet, basename="messaging-message-logs")
router.register(r"email-templates", EmailTemplateViewSet, basename="messaging-email-templates")
router.register(r"template-variables", TemplateVariablesViewSet, basename="messaging-template-variables")

urlpatterns = []

