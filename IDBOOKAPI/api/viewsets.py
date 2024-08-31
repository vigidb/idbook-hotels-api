from django.shortcuts import render
from rest_framework.response import Response
from rest_framework import viewsets, filters, status, mixins, renderers
from django.contrib.auth import login as django_login, logout as django_logout
from rest_framework.authtoken.models import Token
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.utils.timezone import make_aware
from rest_framework.views import APIView
# from rest_framework_tracking.mixins import LoggingMixin
from datetime import timedelta
from datetime import datetime, time, timedelta
# import datetime
import requests, json
from msg91_otp.client import OTPClient
from pyfcm import FCMNotification
import razorpay
from .serializers import *
from IDBOOKAPI.settings import *
from .utils import WORKING_DAYS, SERVICE_CATEGORY_TYPE_CHOICES
from .models import *

# client = razorpay.Client(auth=(razorpay_key, razorpay_secret))
payout_client = razorpay.Client(auth=(razorpay_payout_key, razorpay_payout_secret))
push_service = FCMNotification(api_key=salong_fcm_api_key)
# msg91 API
otp_client = OTPClient(msg91_api_key)  # development
context = {}


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.filter(admin=False)
    serializer_class = UserSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'email', 'mobile', 'first_name', 'last_name', 'gender', 'referral', 'customer',
                        'shop_owner', 'reference', 'paid', 'eligible', 'blocked', 'is_active', 'created']
    # renderer_classes = [renderers.JSONRenderer]

    # def perform_create(self, serializer):
    #     instance = serializer.save()
    #
    #     payload = {}
    #     headers = {
    #         'Authorization': 'Basic {}'.format(rzr_auth_key)
    #     }
    #     check_customer = requests.request("GET", rzr_url+'customers/', headers=headers, data=payload).json()
    #
    #     rzr_customer_id = ''
    #     for i in check_customer['items']:
    #         if serializer.validated_data['email'] == i['email']:
    #             rzr_customer_id = i['id']
    #
    #     if rzr_customer_id == '':
    #         customer_data = {
    #             "name": serializer.validated_data['first_name'].lower() + '.' + serializer.validated_data['mobile'],
    #             "email": serializer.validated_data['email'],
    #             "contact": serializer.validated_data['mobile']
    #             }
    #         r_c_id = payout_client.customer.create(data=customer_data)
    #         instance.razorpay_customer_id = r_c_id['id']
    #     else:
    #         instance.razorpay_customer_id = rzr_customer_id
    #
    #     # contact
    #     contact_data = {"name":serializer.validated_data['first_name'].lower() + '.' + serializer.validated_data['mobile'],
    #                     "email":serializer.validated_data['email'],
    #                     "contact":serializer.validated_data['mobile'],
    #                     "type": "customer",
    #                     "reference_id": "Crazliv Khiladiworld customer"
    #             }
    #     create_contacts = requests.request("POST", rzr_url + 'contacts/', headers=headers, data=contact_data).json()
    #     instance.razorpay_contact_id = create_contacts['id']
    #     instance.set_password(instance.password)
    #     instance.level = instance.level + 1
    #     instance.is_active = True
    #     instance.save()


class FCMTokenViewSet(viewsets.ModelViewSet):
    queryset = FCMToken.objects.all()
    serializer_class = FCMTokenSerializer
    # permission_classes = [IsAuthenticated,]
    # authentication_classes = (BasicAuthentication,)
    http_method_names = ['get', 'post']


class UserCheckViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    # permission_classes = [IsAuthenticated,]
    # authentication_classes = (BasicAuthentication,)
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        mobile = self.request.GET.get('mobile')
        email = self.request.GET.get('email')
        if (mobile and email) is not None:
            qs = User.objects.filter(mobile=mobile, email=email)
            if qs.exists():
                return Response({'msg': True, 'id': qs[0].id, 'mobile': mobile, 'email': email})
            else:
                return Response({'msg': False, 'mobile': mobile, 'email': email})
        elif mobile is not None:
            qs = User.objects.filter(mobile=mobile)
            if qs.exists():
                return Response({'msg': True, 'id': qs[0].id, 'mobile': mobile})
            else:
                return Response({'msg': False, 'mobile': mobile})
        elif email is not None:
            qs = User.objects.filter(email=email)
            if qs.exists():
                return Response({'msg': True, 'id': qs[0].id, 'email': email})
            else:
                return Response({'msg': False, 'email': email})
        return Response({
            'type_1':
                {
                     "request": "[BASE API URL]/api/v1/user-check/?email=test16@gmail.com",
                     'response': {'msg': True, 'email': "test16@gmail.com"}
                  },
            "type_2" :
                {
                    "request": "[BASE API URL]/api/v1/user-check/?mobile=1234554321",
                    'response': {'msg': True, 'mobile': 1234554321}
                },
            "type_3" :
                {
                    "request": "[BASE API URL]/api/v1/user-check/?email=test16@gmail.com&mobile=1234554321",
                    'response': {'msg': True, 'id': 2, 'mobile': 1234554321, 'email': "test16@gmail.com"}}
        })


class ReferenceCheckViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = ReferenceSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = (BasicAuthentication,)
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        referral = self.request.GET.get('referral')
        if referral is not None:
            qs = User.objects.filter(referral=referral)
            if qs.exists():
                u_obj = User.objects.get(referral=referral)
                return Response({'msg': True, 'referral': referral, 'user': u_obj.id})
            else:
                return Response({'msg': False, 'referral': referral})
        return Response({'msg': 'Please enter user referral code'})


class ReferredListViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = ReferredListSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = (BasicAuthentication,)
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        referral = self.request.GET.get('referral')
        if referral is not None:
            qs = User.objects.filter(referral=referral)
            if qs.exists():
                u_obj = User.objects.get(referral=referral)
                main = User.objects.filter(email=u_obj.email)
                u_list = User.objects.filter(reference__in=main)
                serializer = ReferredListSerializer(instance=u_list, many=True)
                return Response({'msg': True, 'referral': referral, 'users': serializer.data})
            else:
                return Response({'msg': False, 'referral': referral})
        return Response({'msg': 'Please enter user referral code'})


class PhoneOTPViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = (BasicAuthentication,)
    http_method_names = ['get']

    def list(self, request, *args, **kwargs):
        mobile = self.request.GET.get('mobile')
        otp = self.request.GET.get('otp')
        # message = "Your One Time Password (OTP) is"
        # sender = "TEST"
        # service_response = otp_client.send_otp(mobile, sender=sender, message=message, country=0)
        service_response = otp_client.send_otp(mobile, otp=otp)
        return Response({'mobile': mobile, 'otp': otp, 'service_response_status': service_response.status,
                        'service_response_message': service_response.message})


# class ProfileDetailViewSet(viewsets.ModelViewSet):
#     queryset = ProfileDetail.objects.all()
#     serializer_class = ProfileDetailSerializer
#     permission_classes = [IsAuthenticated]
#     authentication_classes = (BasicAuthentication,)
#     filter_backends = [DjangoFilterBackend]
#     filterset_fields = ['user',]
#     http_method_names = ['get', 'put', 'patch', 'head', 'options']
#     # http_method_names = ['get', 'post', 'put', 'patch', 'delete', 'head', 'options', 'trace']
#
#     def perform_update(self, serializer):
#         instance = serializer.save()
#         prof_detail_cust = User.objects.get(id=serializer.validated_data['user'].id)
#
#         if not ProfileDetail.objects.get(user=serializer.validated_data['user']).active:
#             new_user_level = prof_detail_cust.level + 1
#             User.objects.filter(id=serializer.validated_data['user'].id).update(level=new_user_level)
#
#         instance.save()

#
# class ServiceCategoryViewSet(viewsets.ModelViewSet):
#     queryset = ServiceCategory.objects.all()
#     serializer_class = ServiceCategorySerializer
#     # permission_classes = [IsAuthenticated]
#     # authentication_classes = (BasicAuthentication,)
#     filter_backends = [DjangoFilterBackend]
#     filterset_fields = ['active',]
#     # http_method_names = ['get', 'put', 'patch', 'head', 'options']


class ShopDetailViewSet(viewsets.ModelViewSet):
    queryset = ShopDetail.objects.all()
    serializer_class = ShopDetailSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'services', 'stylists', 'service_category', 'featured', 'active']
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def create(self, request, *args, **kwargs):
        data = request.data
        serializer = self.get_serializer(data=data)

        if serializer.is_valid():
            serializer.save()
            # for day_name in WORKING_DAYS:
            #     WorkingDay.objects.create(shop_id=data['shop'], day_name=day_name[0])
            return Response(serializer.data)
        else:
            return Response(serializer.errors)


class WorkingDayViewSet(viewsets.ModelViewSet):
    queryset = WorkingDay.objects.all()
    serializer_class = WorkingDaySerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['shop', 'is_working', 'active']
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class GalleryViewSet(viewsets.ModelViewSet):
    queryset = Gallery.objects.all()
    serializer_class = GallerySerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['shop',]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class StylistViewSet(viewsets.ModelViewSet):
    queryset = Stylist.objects.all()
    serializer_class = StylistSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['shop', 'mobile', 'gender', 'experience', 'review', 'active']
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def create(self, request, *args, **kwargs):
        data = request.data
        # data._mutable = True
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            get_stylist = Stylist.objects.get(mobile=data['mobile'])
            update_stylist = ShopDetail.objects.get(id=get_stylist.shop.id)
            update_stylist.stylists.add(get_stylist.id)
            update_stylist.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        instance = self.get_object()
        data = request.data
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            self.perform_update(serializer)
            get_stylist = Stylist.objects.get(mobile=instance.mobile)
            update_stylist = ShopDetail.objects.get(id=get_stylist.shop.id)
            if data['active']:
                update_stylist.stylists.add(get_stylist.id)
                update_stylist.save()
            else:
                update_stylist.stylists.remove(get_stylist.id)
                update_stylist.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['shop', 'service_type', 'active']
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def create(self, request, *args, **kwargs):
        data = request.data
        # data._mutable = True
        serializer = self.get_serializer(data=data)
        if serializer.is_valid():
            serializer.save()
            get_service_type = Service.objects.get(service_type=data['service_type'])
            update_service = ShopDetail.objects.get(id=get_service_type.shop.id)
            update_service.services.add(get_service_type.id)
            update_service.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def update(self, request, pk=None):
        instance = self.get_object()
        data = request.data
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        if serializer.is_valid():
            self.perform_update(serializer)
            get_service_type = Service.objects.get(service_type=instance.service_type)
            update_service = ShopDetail.objects.get(id=get_service_type.shop.id)
            if data['active']:
                update_service.services.add(get_service_type.id)
                update_service.save()
            else:
                update_service.services.remove(get_service_type.id)
                update_service.save()

            return Response(serializer.data, status=status.HTTP_201_CREATED)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CheckAppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all().order_by('-created')
    serializer_class = AppointmentSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    # filter_backends = [DjangoFilterBackend]
    filterset_fields = ['stylist', 'active', 'booked_slot']
    http_method_names = ['get',]

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        stylist = self.request.query_params.get('stylist', None)
        active = self.request.query_params.get('active', None)
        booked_slot_date = self.request.query_params.get('booked_slot', None)

        all_slots = []
        n = 30
        slot_id = 0
        print(all_slots)
        if stylist and booked_slot_date and active.title() != None:
            queryset = queryset.filter(booked_slot__date__gte=booked_slot_date, stylist=stylist, active=active.title())

            if queryset.count() == 0:
                try:
                    get_shop = Stylist.objects.get(id=stylist)
                    get_day_name = datetime.strptime(booked_slot_date, '%Y-%m-%d').strftime("%A")
                    working_time = WorkingDay.objects.get(shop=get_shop.id, day_name=get_day_name)
                    opening_time = working_time.opening_time
                    closing_time = working_time.closing_time
                    shop_opening = opening_time.strftime("%H:%M:%S")
                    shop_closing = closing_time.strftime("%H:%M:%S")
                    shop_opening_new = datetime.strptime(shop_opening, '%H:%M:%S')
                    shop_closing_new = datetime.strptime(shop_closing, '%H:%M:%S')

                    while shop_opening_new <= shop_closing_new:
                        slot_id += 1
                        shop_opening_new = shop_opening_new + timedelta(minutes=n)
                        # print(shop_opening_new)
                        available_slot = shop_opening_new.strftime("%H:%M:%S")
                        available_slot = datetime.strptime(available_slot, '%H:%M:%S')
                        available_slot = available_slot.strftime("%H:%M:%S")
                        # print(available_slot, 'avai............................')
                        all_slots.append({"id": slot_id, "time": available_slot, "available": True})

                except Stylist.DoesNotExist:
                    all_slots.append({"msg": "Query does not matched please try again"})

            else:
                get_shop = Stylist.objects.get(id=stylist)
                booked_slot = queryset[0].booked_slot
                get_day_name = booked_slot.strftime("%A")
                working_time = WorkingDay.objects.get(shop=get_shop.id, day_name=get_day_name)
                opening_time = working_time.opening_time
                closing_time = working_time.closing_time
                shop_opening = opening_time.strftime("%H:%M:%S")
                shop_closing = closing_time.strftime("%H:%M:%S")
                shop_opening_new = datetime.strptime(shop_opening, '%H:%M:%S')
                shop_closing_new = datetime.strptime(shop_closing, '%H:%M:%S')

                while shop_opening_new <= shop_closing_new:
                    slot_id += 1
                    shop_opening_new = shop_opening_new + timedelta(minutes=n)
                    # print(shop_opening_new)
                    available_slot = shop_opening_new.strftime("%H:%M:%S")
                    available_slot = datetime.strptime(available_slot, '%H:%M:%S')
                    available_slot = available_slot.strftime("%H:%M:%S")
                    # print(available_slot, 'else ava........................')
                    all_slots.append({"id": slot_id, "time": available_slot, "available": True})

                obj_slot_id = 0
                for obj in queryset:
                    print(obj.id)
                    get_shop = Stylist.objects.get(id=stylist)
                    booked_slot = obj.booked_slot
                    print(booked_slot, 'booked slot')
                    get_day_name = booked_slot.strftime("%A")
                    working_time = WorkingDay.objects.get(shop=get_shop.id, day_name=get_day_name)
                    opening_time = working_time.opening_time
                    closing_time = working_time.closing_time
                    shop_opening = opening_time.strftime("%H:%M:%S")
                    shop_closing = closing_time.strftime("%H:%M:%S")
                    shop_opening_new = datetime.strptime(shop_opening, '%H:%M:%S')
                    shop_closing_new = datetime.strptime(shop_closing, '%H:%M:%S')
                    exit_time = obj.exit_time
                    print(exit_time)
                    exit_time = exit_time.strftime("%H:%M:%S")
                    booked_slot = booked_slot.strftime("%H:%M:%S")

                    while shop_opening_new <= shop_closing_new:
                        obj_slot_id += 1
                        shop_opening_new = shop_opening_new + timedelta(minutes=n)
                        # print(type(booked_slot_date))
                        # print(booked_slot_date)
                        # available_slot = datetime.now() + timedelta(minutes=n)
                        # print(available_slot, 'shop_opening_new')
                        available_slot = shop_opening_new.strftime("%H:%M:%S")
                        available_slot = datetime.strptime(available_slot, '%H:%M:%S')
                        available_slot = available_slot.strftime("%H:%M:%S")

                        # print(booked_slot <= available_slot < exit_time)
                        # print(booked_slot , available_slot , exit_time)
                        # print(type(booked_slot), type(available_slot), type(exit_time))

                        if booked_slot <= available_slot < exit_time:
                            print('oooooooooooooooooooooooooooooooooooooooooooooooo')
                            all_slots[obj_slot_id - 1]['available'] = False

                    obj_slot_id = 0
        return Response(all_slots, status=status.HTTP_200_OK)


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.all().order_by('-created')
    serializer_class = AppointmentSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    # filter_backends = [DjangoFilterBackend]
    filterset_fields = ['stylist', 'user', 'active', 'booked_slot', 'status']
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        id = self.request.query_params.get('id', None)
        stylist = self.request.query_params.get('stylist', None)
        user = self.request.query_params.get('user', None)
        shop = self.request.query_params.get('shop', None)
        booked_slot_date = self.request.query_params.get('booked_slot', None)
        active = self.request.query_params.get('active', None)
        status = self.request.query_params.get('status', None)
        completed = self.request.query_params.get('completed', None)

        if (stylist and booked_slot_date and active) != None:
            queryset = queryset.filter(booked_slot__date__gte=booked_slot_date, active=active.title(), stylist=stylist)
        elif (stylist and active) != None:
            queryset = queryset.filter(active=active.title(), stylist=stylist)
        elif (stylist and booked_slot_date) != None:
            queryset = queryset.filter(booked_slot__date__gte=booked_slot_date, stylist=stylist)
        elif (booked_slot_date and active) != None:
            queryset = queryset.filter(booked_slot__date__gte=booked_slot_date, active=active.title())
        elif (id and active) != None:
            queryset = queryset.filter(id=id, active=active.title())
        elif user != None:
            queryset = queryset.filter(user=user)
        elif id != None:
            queryset = queryset.filter(id=id)
        elif (shop and status and completed) != None:
            stylist_list = ShopDetail.objects.get(id=shop)
            queryset = queryset.filter(stylist__in=stylist_list.stylist.all(), status=status, completed=completed.title())
        elif (shop and status) != None:
            stylist_list = ShopDetail.objects.get(id=shop)
            queryset = queryset.filter(stylist__in=stylist_list.stylist.all(), status=status)
        elif (shop and completed) != None:
            stylist_list = ShopDetail.objects.get(id=shop)
            queryset = queryset.filter(stylist__in=stylist_list.stylist.all(), completed=completed.title())
        elif shop != None:
            stylist_list = ShopDetail.objects.get(id=shop)
            queryset = queryset.filter(stylist__in=stylist_list.stylist.all())

        serializer = self.get_serializer(instance=queryset, many=True)
        return Response(serializer.data)

    def create(self, request, *args, **kwargs):
        data = request.data
        booked_slot = data['booked_slot']
        # service_time = request.data.getlist('service_taken')
        service_time = data['service_taken']
        data['service_charge'] = 0
        total_service_time = timedelta(0)
        for i in service_time:
            service = Service.objects.get(id=i)
            total_service_time += service.required_time
            data['service_charge'] += service.service_charge

        data['discount'] = 0
        data['total'] = data['service_charge'] - data['discount']
        data['exit_time'] = datetime.strptime(booked_slot, '%Y-%m-%dT%H:%M') + total_service_time
        data['time_required'] = total_service_time
        # data._mutable = False
        get_shop = Stylist.objects.get(id=data['stylist'])

        booked_day = datetime.strptime(booked_slot, '%Y-%m-%dT%H:%M')
        get_day_name = booked_day.strftime("%A")
        working_time = WorkingDay.objects.get(shop=get_shop.shop.id, day_name=get_day_name)

        get_booked_time = booked_day.strftime("%H:%M:%S")
        get_booked_time = datetime.strptime(get_booked_time, "%H:%M:%S")
        get_booked_time = datetime.time(get_booked_time)

        if working_time.opening_time < get_booked_time < working_time.closing_time:
            all_appointments = Appointment.objects.filter(stylist=data['stylist'], active=True,
                                                          booked_slot__contains=booked_slot[0:10])
            if all_appointments.count() > 0:
                for i in all_appointments:
                    if i.booked_slot < make_aware(booked_day) > i.exit_time:
                        serializer = self.get_serializer(data=data)
                        if serializer.is_valid():
                            serializer.save()
                            # FCM notification
                            notification_title = "Appointment Confirmation"
                            notification_body = f"""Hi {data['user'].first_name}, your appointment booked successfully
                             please wait for shop confirmation."""
                            fcm_ids = list(
                                FCMToken.objects.filter(user=data['user'].id, user_type='customer').values_list(
                                    'fcm_token',
                                    flat=True))
                            push_service.notify_multiple_devices(
                                registration_ids=fcm_ids,
                                message_title=notification_title,
                                message_body=notification_body)
                            return Response(serializer.data, status=status.HTTP_201_CREATED)
                        else:
                            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        # FCM notification
                        notification_title = "Apt Not Available"
                        notification_body = f"""Hi {data['user'].first_name}, Sorry appointment not available, 
                        Please try to book on another time."""
                        fcm_ids = list(
                            FCMToken.objects.filter(user=data['user'].id, user_type='customer').values_list(
                                'fcm_token',
                                flat=True))
                        push_service.notify_multiple_devices(
                            registration_ids=fcm_ids,
                            message_title=notification_title,
                            message_body=notification_body)
                        return Response({'msg': "Appointment not available"})
            else:
                serializer = self.get_serializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        else:
            # FCM notification
            notification_title = "Shop Closed!!!"
            notification_body = f"""Hi {data['user'].first_name}, Opps Shop Closed, 
            Please try to book on another time."""
            fcm_ids = list(
                FCMToken.objects.filter(user=data['user'].id, user_type='customer').values_list(
                    'fcm_token',
                    flat=True))
            push_service.notify_multiple_devices(
                registration_ids=fcm_ids,
                message_title=notification_title,
                message_body=notification_body)
            return Response({'msg': "Shop closed"})

    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        data = request.data
        # data._mutable = True
        booked_slot = data['booked_slot']
        # service_time = request.data.getlist('service_taken')
        service_time = data['service_taken']
        data['service_charge'] = 0
        total_service_time = timedelta(0)
        for i in service_time:
            service = Service.objects.get(id=i)
            total_service_time += service.required_time
            data['service_charge'] += service.service_charge

        data['discount'] = 0
        data['total'] = data['service_charge'] - data['discount']
        data['exit_time'] = datetime.strptime(booked_slot, '%Y-%m-%dT%H:%M') + total_service_time
        data['time_required'] = total_service_time
        # data._mutable = False
        get_shop = Stylist.objects.get(id=data['stylist'])
        booked_day = datetime.strptime(booked_slot, '%Y-%m-%dT%H:%M')
        get_day_name = booked_day.strftime("%A")
        working_time = WorkingDay.objects.get(shop=get_shop.id, day_name=get_day_name)

        get_booked_time = booked_day.strftime("%H:%M:%S")
        get_booked_time = datetime.strptime(get_booked_time, "%H:%M:%S")
        get_booked_time = datetime.time(get_booked_time)

        if working_time.opening_time < get_booked_time < working_time.closing_time:
            all_appointments = Appointment.objects.filter(stylist=data['stylist'], active=True)

            if all_appointments.count() > 0:
                for i in all_appointments:
                    if i.booked_slot < make_aware(booked_day) > i.exit_time:
                        serializer = self.get_serializer(instance, data=data, partial=True)
                        if serializer.is_valid():
                            serializer.save()
                            # # FCM notification
                            # notification_title = "Appointment Update"
                            # notification_body = f"""Hi {data['user'].first_name}, your appointment updated successfully
                            #                              please wait for shop confirmation."""
                            # fcm_ids = list(
                            #     FCMToken.objects.filter(user=data['user'].id, user_type='customer').values_list(
                            #         'fcm_token',
                            #         flat=True))
                            # push_service.notify_multiple_devices(
                            #     registration_ids=fcm_ids,
                            #     message_title=notification_title,
                            #     message_body=notification_body)
                            return Response(serializer.data, status=status.HTTP_201_CREATED)
                        else:
                            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                    else:
                        # FCM notification
                        # notification_title = "Apt Not Available"
                        # notification_body = f"""Hi {data['user'].first_name}, Sorry appointment not available,
                        #                         Please try to book on another time."""
                        # fcm_ids = list(
                        #     FCMToken.objects.filter(user=data['user'].id, user_type='customer').values_list(
                        #         'fcm_token',
                        #         flat=True))
                        # push_service.notify_multiple_devices(
                        #     registration_ids=fcm_ids,
                        #     message_title=notification_title,
                        #     message_body=notification_body)
                        return Response({'msg': "Appointment not available"})
            else:
                serializer = self.get_serializer(data=data)
                if serializer.is_valid():
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                else:
                    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        else:
            # FCM notification
            # notification_title = "Shop Closed!!!"
            # notification_body = f"""Hi {data['user'].first_name}, Opps Shop Closed,
            #             Please try to book on another time."""
            # fcm_ids = list(
            #     FCMToken.objects.filter(user=data['user'].id, user_type='customer').values_list(
            #         'fcm_token',
            #         flat=True))
            # push_service.notify_multiple_devices(
            #     registration_ids=fcm_ids,
            #     message_title=notification_title,
            #     message_body=notification_body)
            return Response({'msg': "Shop closed"})

    def destroy(self, request, pk=None):
        context['message'] = "some thing went wrong"
        context['statusCode'] = status.HTTP_403_FORBIDDEN
        context['result'] = "Delete function is not allowed."
        return Response(context)


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'shop', 'active']
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class KYCDocumentViewSet(viewsets.ModelViewSet):
    queryset = KYCDocument.objects.all()
    serializer_class = KYCDocumentSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user',]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def perform_update(self, serializer):
        instance = serializer.save()
        kyc_cust = User.objects.get(id=serializer.validated_data['user'].id)

        if not KYCDocument.objects.get(user=serializer.validated_data['user']).active:
            new_user_level = kyc_cust.level + 1
            User.objects.filter(id=serializer.validated_data['user'].id).update(level=new_user_level)

        instance.save()


class BankDetailViewSet(viewsets.ModelViewSet):
    queryset = BankDetail.objects.all()
    serializer_class = BankDetailSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user',]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def perform_update(self, serializer):
        instance = serializer.save()
        rzr_cust = User.objects.get(id=serializer.validated_data['user'].id)

        if not BankDetail.objects.get(user=serializer.validated_data['user']).active:
            new_user_level = rzr_cust.level + 1
            User.objects.filter(id=serializer.validated_data['user'].id).update(level=new_user_level)

        headers = {
            'Authorization': 'Basic {}'.format(rzr_auth_key),
            'Content-Type': 'application/json'
        }

        # razorpay fund account
        vpa_fund_account_data = {
            "contact_id": rzr_cust.razorpay_contact_id,
            "account_type": "vpa",
            "vpa":
                {
                    "address": serializer.validated_data['upi']
                }
            }
        vpa_result = json.dumps(vpa_fund_account_data)

        create_vpa_fund_account = requests.request("POST", rzr_url + 'fund_accounts', headers=headers,
                                               data=vpa_result).json()
        if 'id' in create_vpa_fund_account.keys():
            razorpay_vpa_fund_account_id = create_vpa_fund_account['id']
        elif 'error' in create_vpa_fund_account.keys():
            raise exceptions.ValidationError({"msg": create_vpa_fund_account['error']['description']})
        else:
            raise exceptions.ValidationError({"msg": "Something went wrong please try again"})

        fund_account_data = {"contact_id": rzr_cust.razorpay_contact_id,
                             "account_type": "bank_account",
                             "bank_account":
                                 {
                                     "name": rzr_cust.get_full_name(),
                                     "ifsc": serializer.validated_data['ifsc'],
                                     "account_number": serializer.validated_data['account_number']
                                  }
                            }

        bank_account_result = json.dumps(fund_account_data)
        create_bank_fund_account = requests.request("POST", rzr_url + 'fund_accounts', headers=headers,
                                               data=bank_account_result).json()
        if 'id' in create_bank_fund_account.keys():
            create_bank_fund_account_id = create_bank_fund_account['id']
        elif 'error' in create_bank_fund_account.keys():
            raise exceptions.ValidationError({"msg": create_bank_fund_account['error']['description']})
        else:
            raise exceptions.ValidationError({"msg": "Something went wrong please try again"})
        instance.razorpay_vpa_fund_account_id = razorpay_vpa_fund_account_id
        instance.razorpay_bank_fund_account_id = create_bank_fund_account_id
        instance.save()


class PayoutCalculationViewSet(viewsets.ModelViewSet):
    queryset = PayoutCalculation.objects.all()
    serializer_class = PayoutCalculationSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user',]


class BannersViewSet(viewsets.ModelViewSet):
    queryset = Banners.objects.filter(active=True)
    serializer_class = BannersSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class DepositViewSet(viewsets.ModelViewSet):
    queryset = Deposit.objects.all()
    serializer_class = DepositSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'status', 'active',]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

#
# class ActiveViewSet(viewsets.ModelViewSet):
#     queryset = Active.objects.all()
#     serializer_class = ActiveSerializer
#     permission_classes = [IsAuthenticated]
#     authentication_classes = (BasicAuthentication,)
#     filter_backends = [DjangoFilterBackend]
#     filterset_fields = ['user', 'status', 'active',]


class WithdrawalViewSet(viewsets.ModelViewSet):
    queryset = Withdrawal.objects.all()
    serializer_class = WithdrawalSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'txn_type', 'status', 'active',]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def create(self, request, *args, **kwargs):
        data = request.data
        serializer = WithdrawalSerializer(data=data)

        if serializer.is_valid():
            w_request = Withdrawal.objects.filter(user=request.data['user'], status='Pending')
            profile_active = User.objects.get(user=request.data['user'])
            bank_detail_active = BankDetail.objects.get(user=request.data['user'])
            kyc_docs_active = KYCDocument.objects.get(user=request.data['user'])

            if not profile_active.is_active:
                return Response({"msg": "Please update Personal Details"})
            elif not bank_detail_active.active:
                return Response({"msg": "Please update Bank Details"})
            elif not kyc_docs_active.active:
                return Response({"msg": "Please update KYC details"})
            elif w_request.count() > 0:
                return Response({"msg": "A withdrawal request already exists please wait till completion."})
            else:
                w_obj = Wallet.objects.get(user=request.data['user'])
                admin_w_obj = AdminWallet.objects.get(id=1)
                total_admin_charges_collected = admin_w_obj.admin_charges_collected + admin_w_obj.admin_charges
                if w_obj.balance > (int(request.data['balance']) + admin_w_obj.admin_charges):

                    previous_withdrawn = User.objects.get(id=request.data['user'])
                    withdrawn = previous_withdrawn.total_withdrawn+int(request.data['balance'])
                    User.objects.filter(id=request.data['user']).update(total_withdrawn=withdrawn)

                    remaining = w_obj.balance - (int(request.data['balance']) + admin_w_obj.admin_charges)
                    Wallet.objects.filter(user=request.data['user']).update(balance=remaining)
                    AdminWallet.objects.filter(id=1).update(admin_charges_collected=total_admin_charges_collected)
                    Transaction.objects.create(user=User.objects.get(id=request.data['user']),
                                               balance=request.data['balance'],
                                               txn_type='Debit',
                                               info='You withdrawn {}'.format(request.data['balance']),
                                               method='Account Withdraw', status='Pending')
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_201_CREATED)
                else:
                    return Response({"msg": "insufficient balance!!"})
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TransactionViewSet(viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'txn_type', 'status', 'active',]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class AdminWalletViewSet(viewsets.ModelViewSet):
    queryset = AdminWallet.objects.filter(id=1)
    serializer_class = AdminWalletSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class WalletViewSet(viewsets.ModelViewSet):
    queryset = Wallet.objects.all()
    serializer_class = WalletSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['user', 'balance', 'active',]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class PayCalculationViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    # filterset_fields = ['match_id', 'active', 'fixture',]

    def list(self, request, *args, **kwargs):
        id_ = self.request.query_params.get('id', None)
        total_amount = 0
        earnings = 0
        qs = User.objects.filter(mega_customer=True, admin=False).order_by('created')
        l = []
        total_referral = 0
        for i in qs:
            main = User.objects.filter(pk=i.id)
            total_amount += i.joining
            context = User.objects.filter(reference__in=main).filter(mega_customer=True)
            total_referral += context.count()
            if context.count() >= 1:
                earnings += (((i.joining/2)/total_referral)*context.count())

            r_ids = []
            for ids in context:
                r_ids.append(ids.id)

            l.append({"id": i.id, "email": i.email, 'qs': r_ids, "total": context.count(),
                      "earnings": earnings, "created": i.created,
                      "total_amount": total_amount})
            earnings = 0

        return Response(l)


class NotificationViewSet(viewsets.ModelViewSet):
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    search_fields = ['user',]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


# class ServiceCategoryViewSet(viewsets.ModelViewSet):
#     queryset = ServiceCategory.objects.all()
#     serializer_class = ServiceCategorySerializer
#     # permission_classes = [IsAuthenticated]
#     # authentication_classes = (BasicAuthentication,)
#     filter_backends = [filters.SearchFilter]
#     search_fields = ['user',]
#     http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    # def create(self, request, *args, **kwargs):
    #     listOfThings = request.data['categories']
    #
    #     serializer = self.get_serializer(data=listOfThings, many=True)
    #     if serializer.is_valid():
    #         serializer.save()
    #         headers = self.get_success_headers(serializer.data)
    #         return Response(serializer.data, status=status.HTTP_201_CREATED,
    #                         headers=headers)
    #
    #     return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class CommentViewSet(viewsets.ModelViewSet):
#     queryset = Comment.objects.all()
#     serializer_class = CommentSerializer
#     permission_classes = [IsAuthenticated]
#     authentication_classes = (BasicAuthentication,)
#     filter_backends = [filters.SearchFilter]
#     search_fields = ['user',]
#     http_method_names = ['get', 'post', 'put', 'patch', 'head', ]


class EnquiryViewSet(viewsets.ModelViewSet):
    queryset = Enquiry.objects.all()
    serializer_class = EnquirySerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend, ]
    filterset_fields = ['id', 'subject', 'user', 'replied_by', 'active', 'created', 'updated']
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class AboutUsViewSet(viewsets.ModelViewSet):
    queryset = AboutUs.objects.all()
    serializer_class = AboutUsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'title', 'active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class PrivacyPolicyViewSet(viewsets.ModelViewSet):
    queryset = PrivacyPolicy.objects.all()
    serializer_class = PrivacyPolicySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'title', 'active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class RefundAndCancellationPolicyViewSet(viewsets.ModelViewSet):
    queryset = RefundAndCancellationPolicy.objects.all()
    serializer_class = RefundAndCancellationPolicySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'title', 'active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class TermsAndConditionsViewSet(viewsets.ModelViewSet):
    queryset = TermsAndConditions.objects.all()
    serializer_class = TermsAndConditionsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'title', 'active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class LegalityViewSet(viewsets.ModelViewSet):
    queryset = Legality.objects.all()
    serializer_class = LegalitySerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'title', 'active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class CareerViewSet(viewsets.ModelViewSet):
    queryset = Career.objects.all()
    serializer_class = CareerSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'title', 'active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class FAQsViewSet(viewsets.ModelViewSet):
    queryset = FAQs.objects.all().order_by('id')
    serializer_class = FAQsSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'title', 'active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']


class PaymentGatewayViewSet(viewsets.ModelViewSet):
    queryset = PaymentGateway.objects.filter(active=True).order_by('created')
    serializer_class = PaymentGatewaySerializer
    # permission_classes = [IsAuthenticated]
    # authentication_classes = (BasicAuthentication,)
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['id', 'provider', 'enabled', 'active', ]
    # http_method_names = ['get', 'post', 'put', 'patch', 'head', 'options']

    def list(self, request, *args, **kwargs):
        context = []
        for i in self.get_queryset():
            pgp = {"RAZORPAY": {"key": razorpay_key, "secret": razorpay_secret, "mode": "test"},
                   "CASHFREE": {"key": cashfree_client_id, "secret": cashfree_client_secret, "mode": "test"},
                   "PAYTM": {"key": "", "secret": "", "mode": "test"}
                  }
            for key in pgp.keys():
                if i.provider == key:
                    context.append({
                        "id": i.id,
                        "provider": i.provider,
                        "enabled": i.enabled,
                        "mode": pgp[i.provider]['mode'],
                        "key": pgp[i.provider]['key'],
                        "secret": pgp[i.provider]['secret']
                    })

        return Response(context)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        django_login(request, user)
        token, created = Token.objects.get_or_create(user=user)
        return Response({'token': token.key}, status=200)


class LogoutView(APIView):
    authentication_classes = (BasicAuthentication, )

    def post(self, request):
        django_logout(request)
        return Response(status=204)


class BasicAuthKeyViewSet(APIView):
    def get(self, request):
        return Response({"basic_auth_key":basic_auth_key}, status=200)


class ServiceCategoryViewSet(APIView):
    def get(self, request):
        service_categories = []
        for service in SERVICE_CATEGORY_TYPE_CHOICES:
            # service_categories.append(service[0])
            d = {"name": service[0], "icon": "https://resources.salong.in/static/service_categories/{}.png".format(service[0])}
            service_categories.append(d)

        return Response(service_categories, status=200)
