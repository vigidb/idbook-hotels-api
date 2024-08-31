from rest_framework import serializers
from datetime import timedelta
import re
from .models import (TourPackage, Accommodation, InclusionExclusion, Vehicle, DailyPlan, TourBankDetail,
                     CustomerTourEnquiry)
from IDBOOKAPI.utils import format_custom_id, format_tour_duration
from IDBOOKAPI.basic_resources import TOUR_DURATION_CHOICES


class TourPackageSerializer(serializers.ModelSerializer):
    formatted_tour_duration = serializers.SerializerMethodField(read_only=True)
    formatted_tour_duration_full = serializers.SerializerMethodField(read_only=True)
    check_out_date = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = TourPackage
        fields = ('id', 'trip_id', 'trip_name', 'customer_fullname', 'tour_duration', 'date_of_journey', 'adults',
                  'tour_start_city', 'total_booking_amount', 'advance_amount_to_pay_for_the_trip_confirmation',
                  'payment_link', 'formatted_tour_duration', 'formatted_tour_duration_full', 'check_out_date')
        # extra_kwargs = {'trip_id': {'write_only': True}}

    def create(self, validated_data):
        trip_name = validated_data.get('trip_name')

        tour = TourPackage(**validated_data)
        tour.save()
        tour.trip_id = format_custom_id(trip_name.upper()[0:4], tour.id)
        tour.active = True
        tour.save()

        return tour

    def get_formatted_tour_duration(self, obj):
        try:
            return dict(TOUR_DURATION_CHOICES).get(int(obj.tour_duration))
        except ValueError:
            return obj.tour_duration

    def get_formatted_tour_duration_full(self, obj):
        formatted_duration = self.get_formatted_tour_duration(obj)
        return format_tour_duration(formatted_duration)

    def get_check_out_date(self, obj):
        if obj.date_of_journey and obj.tour_duration:
            try:
                tour_duration = int(obj.tour_duration)
            except ValueError:
                match = re.search(r'^(\d+)', obj.tour_duration)
                if match:
                    tour_duration = int(match.group(1))
            return (obj.date_of_journey + timedelta(days=tour_duration)).isoformat()
        return None


class AccommodationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Accommodation
        fields = '__all__'


class InclusionExclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = InclusionExclusion
        fields = '__all__'


class VehicleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehicle
        fields = '__all__'


class DailyPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = DailyPlan
        fields = '__all__'


class TourBankDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = TourBankDetail
        fields = '__all__'


class CustomerTourEnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerTourEnquiry
        fields = '__all__'
