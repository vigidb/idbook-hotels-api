from django.db import models
from apps.authentication.models import User

# Create your models here.


class BusinessDetail(models.Model):
     user = models.ForeignKey(User, on_delete=models.CASCADE,
                              related_name='business_detail')
     business_name = models.CharField(max_length=50)
     business_logo = models.URLField(blank=True)
     business_phone = models.CharField(max_length=50)
     business_email = models.CharField(max_length=50)
     country = models.CharField(max_length=25, default='INDIA')
     created = models.DateTimeField(auto_now_add=True)
     updated = models.DateTimeField(auto_now=True)

     class Meta:
         ordering =('created',)

     def __str__(self):
         return str(self.business_name)
    



