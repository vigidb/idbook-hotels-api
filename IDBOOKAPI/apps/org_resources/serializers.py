from rest_framework import serializers
from django.contrib.auth.models import Permission, Group
from django.contrib.auth import authenticate
from IDBOOKAPI.img_kit import upload_media_to_bucket
from apps.authentication.models import User
from .models import (
    CompanyDetail, AmenityCategory, Amenity, Enquiry, RoomType, Occupancy, Address,
    AboutUs, PrivacyPolicy, RefundAndCancellationPolicy, TermsAndConditions, Legality,
    Career, FAQs, UploadedMedia, CountryDetails, UserNotification
)
from apps.org_resources import db_utils as org_res_db_utils
from apps.org_managements import utils as org_mng_utils


class CompanyDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyDetail
        exclude = ('added_user', )

##    def validate_company_email(self, value):
####        if not value:
####             raise serializers.ValidationError(
####                 {'message': 'Company email missing'})
##        
##        if value:
##            company_detail = CompanyDetail.objects.filter(company_email=value).first()
##            if company_detail:
##                raise serializers.ValidationError(
##                 {'message': 'Company email already present'})
##        return value
            

    def create(self, validated_data):
        try:
            request = self.context.get('request')
            company_email = validated_data.get('company_email', '')
            company_phone = validated_data.get('company_phone', '')
            print("company email::", company_email)
            company_detail = CompanyDetail(**validated_data)

            try:
                if request.user:
                    company_detail.added_user = request.user
                    company_detail.approved = True
            except Exception as e:
                print("Added User Empty for Company Create", e)
                
            company_detail.save()
            return company_detail
        except Exception as e:
            raise serializers.ValidationError(
                {'message': 'Internal Server Error'})

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        company = instance
        if company and company.business_rep:
            brep_name = company.business_rep.name
            brep_email = company.business_rep.email
            brep_mobile_number = company.business_rep.mobile_number
            ret['business_rep'] = {"name":brep_name, "email":brep_email,
                                   "mobile_number":brep_mobile_number}
        return ret


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

class CountryDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CountryDetails
        fields = '__all__'

class UserNotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserNotification
        fields = '__all__'

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        send_user  = instance.send_by
        sender_profile_pic = ""
        if send_user:
            business_id = send_user.business_id
            company_id = send_user.company_id
            if company_id:
                company_details = org_res_db_utils.get_company_details(company_id)
                if company_details and company_details.company_logo:
                    sender_profile_pic = company_details.company_logo.url
            elif business_id:
                bdetails = org_mng_utils.get_business_details(business_id)
                if bdetails and bdetails.business_logo:
                    sender_profile_pic = bdetails.business_logo.url

            if not sender_profile_pic:
                if send_user.customer_profile:
                    customer = send_user.customer_profile.last()
                    if customer and customer.profile_picture:
                        sender_profile_pic = customer.profile_picture.url

            ret['send_by'] = {'name':send_user.name, 'email':send_user.email,
                              'profile_pic':sender_profile_pic}
        return ret

