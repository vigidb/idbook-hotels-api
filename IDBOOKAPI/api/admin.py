# from django.contrib import admin
# from api.models import Hotel, Room, Reviews
#
#
#
# class HotelInline(admin.TabularInline):
#     model = Room
#     extra = 1
#
# @admin.register(Hotel)
# class HotelAdmin(admin.ModelAdmin):
#     list_display = ['id', 'city', 'title', 'postal_code', 'starting_price','hourly_booking',
#                     'featured', 'active', 'author', 'created', 'updated']
#     list_display_links = ['id', 'city', 'title',]
#     list_filter = ['city', 'couple_friendly', 'hourly_booking', 'created', 'updated']
#     list_editable = ['featured', 'active', 'hourly_booking']
#     fieldsets = (
#         ('Hotel Info (Required)', {
#             'fields': (tuple(['title', 'slug', 'city', 'starting_price', 'discount', 'author', 'featured', 'active']),)
#         },),
#         ('Hotel Address Info (Required)', {
#             'fields': (tuple(['address', 'state', 'postal_code']),)
#         }),
#         ('Hotel Geographical Location (Optional)', {
#             'fields': (tuple(['latitude', 'longitude']),)
#         }),
#         ('Hotel Contact Info (Required)', {
#             'fields': (tuple(['email', 'phone_no', 'picture', 'description']),)
#         }),
#         ('Hotel Facilities (Required)', {
#             'fields': (tuple(['elevator', 'wifi', 'fitness_center', 'taxi',
#                        'breakfast', 'parking', 'air_condition', 'smoking_zone',
#                        'wheelchair', 'restaurant', 'couple_friendly', 'hourly_booking']),)
#         }),
#         ('Hotel Manager Details (Optional)', {
#             'fields': (tuple(['manager_name', 'manager_gender', 'manager_age', 'manager_contact_no', 'manager_photo',
#                               'manager_detail']),)
#         }),
#         ('Hotel Representative Details (Required)', {
#             'fields': (tuple(['person_name', 'gender', 'person_age', 'contact_no', 'person_photo', 'person_detail']),)
#         }),
#         ('Hotel Room Pictures (Required)- Note: Please upload high quality pictures for better response.', {
#             'fields': (tuple(['room_picture_1', 'room_picture_2', 'room_picture_3',
#                               'room_picture_4', 'room_picture_5', 'room_picture_6',
#                               'room_picture_7', 'room_picture_8', 'room_picture_9']),)
#         }),
#     )
#
#     inlines = [HotelInline]
#     search_fields = ['city', 'title', 'postal_code']
#     prepopulated_fields = {'slug': ('title',)}
#
#     def get_prepopulated_fields(self, request, obj=None):
#         return {'slug': ('title',)}
#
#
# @admin.register(Reviews)
# class ReviewsAdmin(admin.ModelAdmin):
#     list_display = ('id', 'name', 'email', 'hotel', 'created', 'active')
#     list_filter = ('active', 'created', 'updated')
#     search_fields = ('name', 'email', 'body')
#
#
#
