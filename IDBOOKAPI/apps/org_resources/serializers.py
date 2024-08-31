from rest_framework import serializers
from django.contrib.auth.models import Permission, Group
from django.contrib.auth import authenticate
from IDBOOKAPI.img_kit import upload_media_to_bucket
from .models import (
    CompanyDetail, AmenityCategory, Amenity, Enquiry, RoomType, Occupancy, Address,
    AboutUs, PrivacyPolicy, RefundAndCancellationPolicy, TermsAndConditions, Legality, Career, FAQs, UploadedMedia
)


class CompanyDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyDetail
        fields = '__all__'


class UploadedMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UploadedMedia
        fields = '__all__'

    def create(self, validated_data, *args, **kwargs):
        user = self.context['request'].user
        file_name = validated_data.get('file_name')
        file_path = self.context['request'].FILES['file_path']
        tags = validated_data.get('tags')
        media_instance = UploadedMedia(**validated_data)
        media_instance.save()

        res = upload_media_to_bucket(file_name=file_name, file_path=file_path, tags=tags)

        media_instance.file_id = res['fileId']
        media_instance.title = file_name.title()
        media_instance.url = res['url']
        media_instance.thumbnail_url = res['thumbnailUrl']
        media_instance.tags = res['tags']
        media_instance.size = res['size']
        media_instance.height = res['height']
        media_instance.width = res['width']
        media_instance.type = res['fileType']
        media_instance.version_id = res['versionInfo']['id']
        media_instance.version_name = res['versionInfo']['name']
        media_instance.user = user
        media_instance.active = True
        media_instance.save()
        return media_instance


class AmenityCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = AmenityCategory
        fields = '__all__'


class AmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Amenity
        fields = '__all__'


class RoomTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomType
        fields = '__all__'


class OccupancySerializer(serializers.ModelSerializer):
    class Meta:
        model = Occupancy
        fields = '__all__'


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = '__all__'


class EnquirySerializer(serializers.ModelSerializer):
    class Meta:
        model = Enquiry
        fields = '__all__'


class AboutUsSerializer(serializers.ModelSerializer):
    class Meta:
        model = AboutUs
        fields = '__all__'


class PrivacyPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = PrivacyPolicy
        fields = '__all__'


class RefundAndCancellationPolicySerializer(serializers.ModelSerializer):
    class Meta:
        model = RefundAndCancellationPolicy
        fields = '__all__'


class TermsAndConditionsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TermsAndConditions
        fields = '__all__'


class LegalitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Legality
        fields = '__all__'


class CareerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Career
        fields = '__all__'


class FAQsSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQs
        fields = '__all__'
