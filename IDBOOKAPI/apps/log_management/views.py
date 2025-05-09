from rest_framework import viewsets
from rest_framework import status
from rest_framework.decorators import action

from django.conf import settings

from IDBOOKAPI.mixins import StandardResponseMixin, LoggingMixin
from IDBOOKAPI.utils import paginate_queryset, validate_date

from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.log_management.models import UserSubscriptionLogs
from apps.log_management.serializers import UserSubscriptionLogsSerializer

from django.db.models import Q


class UserSubscriptionLogsViewSet(viewsets.ModelViewSet, StandardResponseMixin, LoggingMixin):
    queryset = UserSubscriptionLogs.objects.all()
    serializer_class = UserSubscriptionLogsSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ['get']

    def user_subscription_param_ops(self):
        
        filter_dict = {}
        # fetch filter parameters
        param_dict= self.request.query_params
        for key in param_dict:
            if key in ('user', 'user_sub', 'status_code'):
                filter_dict[key] = param_dict[key]

        if filter_dict:
            self.queryset = self.queryset.filter(**filter_dict)

        # search 
        search = self.request.query_params.get('search', '')
        if search:
            search_q_filter = Q(pg_subid__icontains=search) | Q(tnx_id__icontains=search)
            self.queryset = self.queryset.filter(search_q_filter)

    def property_order_ops(self):
        ordering_params = self.request.query_params.get('ordering', None)
        if ordering_params:
            ordering_list = ordering_params.split(',')
            self.queryset = self.queryset.order_by(*ordering_list)

    def list(self, request, *args, **kwargs):
        
        # filtering and ordering
        self.user_subscription_param_ops()
        self.property_order_ops()

        count, self.queryset = paginate_queryset(self.request,  self.queryset)
        

        # Perform the default listing logic
        response = super().list(request, *args, **kwargs)

        if response.status_code == status.HTTP_200_OK:
            # If the response status code is OK (200), it's a successful listing
            custom_response = self.get_response(
                data=response.data,  # Use the data from the default response
                status='success',
                message="List Retrieved",
                count=count,
                status_code=status.HTTP_200_OK,  # 200 for successful listing

            )
        else:
            # If the response status code is not OK, it's an error
            custom_response = self.get_response(
                data=None,
                message="Error Occurred",
                status_code=response.status_code,  # Use the status code from the default response
                is_error=True
            )

        return custom_response

    

    
