from rest_framework import serializers

from apps.log_management.models import UserSubscriptionLogs

class UserSubscriptionLogsSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserSubscriptionLogs
        fields = '__all__'

