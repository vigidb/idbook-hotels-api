from rest_framework import serializers
from django.contrib.auth.models import Permission, Group
from django.contrib.auth import authenticate

from IDBOOKAPI.img_kit import upload_media_to_bucket
from .models import (Property, Gallery, Room, Rule,
                     Inclusion, FinancialDetail, HotelAmenityCategory,
                     HotelAmenity, RoomAmenityCategory, RoomAmenity,
                     PropertyGallery, RoomGallery, PropertyBankDetails)
from IDBOOKAPI.utils import format_custom_id, find_state
from ..org_resources.models import UploadedMedia
from ..org_resources.serializers import UploadedMediaSerializer
from apps.hotels.utils.db_utils import (
    get_property_featured_image, get_rooms_by_property, get_starting_room_price,
    get_slot_based_starting_room_price, get_property_gallery)

from django.conf import settings


class PropertyGallerySerializer(serializers.ModelSerializer):

    class Meta:
        model = PropertyGallery
        fields = '__all__'
        
class PropertySerializer(serializers.ModelSerializer):
    custom_id = serializers.ReadOnlyField()
    class Meta:
        model = Property
        fields = '__all__'

    def create(self, validated_data):
        user = self.context['request'].user
        property_instance = Property(**validated_data)
        property_instance.added_by = user
        property_instance.save()
        return property_instance

class PropertyListSerializer(serializers.ModelSerializer):

    class Meta:
        model = Property
        fields = ('id','name', 'title', 'property_type',
                  'rental_form', 'review_star', 'review_count',
                  'additional_fields', 'area_name',
                  'city_name', 'state', 'country', 'rating',
                  'status', 'current_page', 'address', 'starting_price_details')
        
    def to_representation(self, instance):
        representation = super().to_representation(instance)
        available_property_dict = self.context.get("available_property_dict", {})
        favorite_list = self.context.get("favorite_list", [])
        # nonavailable_property_list = self.context.get("nonavailable_property_list", [])
        #print("available property dict::", available_property_dict)
        if instance:
            gallery = None
##            property_id = instance.get('id', None)
            property_id = instance.id
            if property_id:
                
##                gallery = get_property_featured_image(property_id)
##            if gallery and gallery.media:
##                representation['featured_image'] = settings.MEDIA_URL + str(gallery.media)
##            else:
##                representation['featured_image'] = ""

##                gallery_property = get_property_gallery(property_id)
##
##                if gallery_property:
##                    property_gallery = list(gallery_property.values('media', 'caption', 'featured_image'))
##                    for gallery in property_gallery:
##                        gallery['media'] = settings.MEDIA_URL + str(gallery.get('media', ''))
##                    representation['property_gallery'] = property_gallery
##                else:
##                    representation['property_gallery'] = []

                representation['property_gallery'] = []
            avail_prop = available_property_dict.get(property_id, None)
            if avail_prop:
                representation['available_room_after_booking'] = avail_prop
            else:
                representation['available_room_after_booking'] = {}

            if property_id in favorite_list:
                representation['favorite'] = True
            else:
                representation['favorite'] = False

            if property_id:
                starting_room_price = get_starting_room_price(property_id)
                representation['starting_room_price'] = starting_room_price
                # starting_price_list = get_slot_based_starting_room_price(property_id)
                # representation['starting_price_list'] = starting_price_list

##            if property_id in nonavailable_property_list:
##                representation['available'] = False
##            else:
##                representation['available'] = True

        return representation     

##    def create(self, validated_data):
##        user = self.context['request'].user
##        amenity = validated_data.pop('amenity')
##        property_instance = Property(**validated_data)
##        property_instance.save()
##        initials = ''.join(word[0] for word in property_instance.service_category.split()).replace('&','')
##        property_instance.custom_id = format_custom_id(initials, property_instance.id)
##        property_instance.state = find_state(property_instance.city_name)
##        property_instance.added_by = user
##        property_instance.save()
##        property_instance.amenity.set(amenity)
##        return property_instance


class RoomGallerySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomGallery
        fields = '__all__'
        
class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = '__all__'

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        
        if instance and instance.gallery_room:
            room_gallery = list(instance.gallery_room.filter(active=True).values(
                'media', 'caption', 'featured_image'))
            for gallery in room_gallery:
                gallery['media'] = settings.MEDIA_URL + str(gallery.get('media', ''))
            representation['room_gallery'] = room_gallery
        else:
            representation['room_gallery'] = []
            
        return representation 
            
            

class PropertyRoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ('id','name', 'room_type', 'room_view',
                  'no_available_rooms', 'room_price',
                  'room_occupancy', 'is_slot_price_enabled')

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance:
            if instance.gallery_room:
##                gallery = instance.gallery_room.filter(featured_image=True).first() 
##                if gallery and gallery.media:
##                    representation['featured_image'] = settings.MEDIA_URL + str(gallery.media)
##                else:
##                    representation['featured_image'] = ""
                room_gallery = list(instance.gallery_room.filter(active=True).values(
                    'media', 'caption', 'featured_image'))
                for gallery in room_gallery:
                    gallery['media'] = settings.MEDIA_URL + str(gallery.get('media', ''))
                representation['room_gallery'] = room_gallery
            else:
                representation['room_gallery'] = []

        return representation 

class PropertyRetrieveSerializer(serializers.ModelSerializer):

    property_room = PropertyRoomSerializer(many=True)


    class Meta:
        model = Property
        exclude = ('legal_document', )

##    def fetch_rooms(self, property_id):
##        available_room_after_booking = self.context.get("available_room_after_booking", {}))
##        rooms = get_rooms_by_property(property_id)
##        serializer = PropertyRoomSerializer(
##            rooms, many=True, context={
##                'available_room_after_booking': available_room_after_booking})
##        
##        return serializer.data

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        if instance:
            # property gallery
##            room_details = self.fetch_rooms(instance.id)
##            representation['property_room'] = room_details
            
            if instance.gallery_property:
                property_gallery = list(instance.gallery_property.values('media', 'caption', 'featured_image'))
                for gallery in property_gallery:
                    gallery['media'] = settings.MEDIA_URL + str(gallery.get('media', ''))
                representation['property_gallery'] = property_gallery
            else:
                representation['property_gallery'] = []

            # legal document
            if instance.legal_document:
                representation['legal_document'] = settings.MEDIA_URL + str(instance.legal_document)
        
        return representation


class GallerySerializer(serializers.ModelSerializer):
    # property = PropertySerializer(read_only=True)
    # room = RoomSerializer(read_only=True)
    media = UploadedMediaSerializer(read_only=True)
    class Meta:
        model = Gallery
        fields = '__all__'

    def create(self, validated_data):
        user = self.context['request'].user
        request_data = self.context['request'].data

        file_name = request_data.get('file_name', [])
        file_path = self.context['request'].FILES.get('file_path')
        tags = request_data.get('tags', [])

        if file_path:
            res = upload_media_to_bucket(file_name=file_name, file_path=file_path, tags=tags)

            media_instance = UploadedMedia(
                file_id=res['fileId'],
                title=file_name.title(),
                file_name=file_name,
                url=res['url'],
                thumbnail_url=res['thumbnailUrl'],
                # tags=res['tags'],
                tags=tags,
                size=res['size'],
                height=res['height'],
                width=res['width'],
                type=res['fileType'],
                version_id=res['versionInfo']['id'],
                version_name=res['versionInfo']['name'],
                user=user,
                active=True
            )
            media_instance.save()

            property_data = request_data.get('property')
            room_data = request_data.get('room')

            if property_data:
                property_instance = Property.objects.get(id=property_data)
                gallery_instance = Gallery(
                    added_by=user, media=media_instance, property=property_instance)
                gallery_instance.save()
                return gallery_instance

            elif room_data:
                room_instance = Room.objects.get(id=room_data)
                gallery_instance = Gallery(
                    added_by=user, media=media_instance, room=room_instance)
                gallery_instance.save()
                return gallery_instance

        else:
            raise serializers.ValidationError("File path is missing in payload.")


class RuleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Rule
        fields = '__all__'


class InclusionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inclusion
        fields = '__all__'


class FinancialDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = FinancialDetail
        fields = '__all__'


##class ReviewSerializer(serializers.ModelSerializer):
##    class Meta:
##        model = Review
##        fields = '__all__'

class HotelAmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = HotelAmenity
        fields = '__all__'

class HotelAmenityCategorySerializer(serializers.ModelSerializer):
    hotel_amenity = HotelAmenitySerializer(read_only=True, many=True)
    class Meta:
        model = HotelAmenityCategory
        fields = ('id', 'title', 'active', 'hotel_amenity')

class RoomAmenitySerializer(serializers.ModelSerializer):
    class Meta:
        model = RoomAmenity
        fields = ('id', 'title', 'active', 'detail')

class RoomAmenityCategorySerializer(serializers.ModelSerializer):
    room_amenity = RoomAmenitySerializer(read_only=True, many=True)
    class Meta:
        model = RoomAmenityCategory
        fields = ('id', 'title', 'active', 'room_amenity')

class PropertyBankDetailsSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyBankDetails
        fields = '__all__'


