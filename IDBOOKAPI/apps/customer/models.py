from django.db import models
from apps.authentication.models import User
from apps.org_resources.models import Address
from IDBOOKAPI.basic_resources import GENDER_CHOICES, KYC_DOCUMENT_CHOICES, LANGUAGES_CHOICES


class Customer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             verbose_name="customer_profile",
                             help_text="user profile in user table")
    added_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name="customer_profiles", null=True,blank=True)
    address = models.ForeignKey(Address, on_delete=models.CASCADE, null=True, blank=True,
                                verbose_name="customer_address")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True,
                              help_text="Select the gender of the customer."
                              )
    date_of_birth = models.DateField(null=True, blank=True,
                                     help_text="Enter the date of birth of the customer.")
    profile_picture = models.URLField(default='')
    id_proof_type = models.CharField(max_length=20, choices=KYC_DOCUMENT_CHOICES,
                                     blank=True, null=True,)
    id_proof = models.URLField(default='')
    pan_card = models.URLField(default='')
    pan_card_number = models.CharField(max_length=20, blank=True, null=True,)
    aadhar_card = models.URLField(default='')
    aadhar_card_number = models.CharField(max_length=20, blank=True, null=True,)

    loyalty_points = models.PositiveIntegerField(default=0, help_text="Total loyalty points earned by the customer.")
    membership_status = models.BooleanField(default=False, help_text="Check if the customer has a membership.")
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True,
                                              help_text="Name of the customer's emergency contact person.")
    emergency_contact_phone = models.CharField(max_length=10, blank=True, null=True,
                                               help_text="Phone number of the customer's emergency contact.")
    preferred_language = models.CharField(max_length=20, blank=True, choices=LANGUAGES_CHOICES,
                                          help_text="Preferred language of communication for the customer.")
    dietary_restrictions = models.TextField(blank=True,
                                            help_text="Any dietary restrictions or preferences for the customer.")
    special_requests = models.TextField(blank=True, help_text="Any special requests or notes from the customer.")

    privileged = models.BooleanField(default=False, help_text="Whether the customer is privileged.")
    active = models.BooleanField(default=False, help_text="Whether the customer is active.")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"
