#from django.contrib.auth.models import User
from apps.authentication.models import User
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
# from rest_framework.authtoken.models import Token

from IDBOOKAPI.utils import unique_referral_id_generator


##@receiver(post_save, sender=User)
##def create_auth_token(sender, instance=None, created=False, **kwargs):
##    if created:
##        Token.objects.create(user=instance)

@receiver(pre_save, sender=User)
def user_before_save(sender, instance:User, **kwargs):
    print("*********before save")
    if not instance.referral:
        instance.referral = unique_referral_id_generator(instance)
        
