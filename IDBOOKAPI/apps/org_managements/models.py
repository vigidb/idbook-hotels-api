from django.db import models
from apps.authentication.models import User

# Create your models here.


class BusinessDetail(models.Model):
     user = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='business_detail')
     business_name = models.CharField(max_length=150)
     hsn_sac_no = models.CharField(max_length=100, null=True)
     business_logo = models.FileField(upload_to='business/logo/', blank=True, null=True)
     business_phone = models.CharField(max_length=50, blank=True, null=True)
     business_email = models.CharField(max_length=50, blank=True, null=True)
     domain_name = models.CharField(max_length=50, blank=True, null=True)
     full_address = models.CharField(max_length=500, blank=True, null=True)
     gstin_no = models.CharField(max_length=100, blank=True, null=True)
     pan_no = models.CharField(max_length=100, blank=True, null=True)
     website_url = models.URLField(blank=True)
     country = models.CharField(max_length=25, default='INDIA')
     active = models.BooleanField(default=False, help_text="Whether the business is active.")
     created = models.DateTimeField(auto_now_add=True)
     updated = models.DateTimeField(auto_now=True)

     class Meta:
         ordering =('created',)

     def __str__(self):
         return str(self.business_name)
    



