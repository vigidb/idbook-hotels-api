from rest_framework import serializers
from apps.analytics.models import PropertyAnalytics

class PropertyAnalyticsSerializer(serializers.ModelSerializer):

    class Meta:
        model = PropertyAnalytics
        fields = '__all__'
