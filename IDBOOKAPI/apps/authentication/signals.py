# from django.contrib.auth.models import User
from apps.authentication.models import User
from apps.authentication.constants import ALL_GROUP_CHOICES
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

# from rest_framework.authtoken.models import Token

from IDBOOKAPI.utils import unique_referral_id_generator
from apps.messaging.services import upsert_contact_for_registered_user


##@receiver(post_save, sender=User)
##def create_auth_token(sender, instance=None, created=False, **kwargs):
##    if created:
##        Token.objects.create(user=instance)


@receiver(pre_save, sender=User)
def user_before_save(sender, instance: User, **kwargs):
    print("*********before save")
    if not instance.referral:
        instance.referral = unique_referral_id_generator(instance)


@receiver(post_save, sender=User)
def sync_user_to_messaging_contact(sender, instance: User, **kwargs):
    """
    Keep messaging contacts in sync with newly registered/updated users.
    This allows campaigns with registered_only targeting to include new signups automatically.
    """
    group_type = (instance.default_group or "").strip()
    allowed_group_values = set(dict(ALL_GROUP_CHOICES).keys())
    if not group_type and not instance.groups.filter(name__in=allowed_group_values).exists():
        return
    upsert_contact_for_registered_user(instance, source="registration_sync")
