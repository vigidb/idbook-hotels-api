from django.db import models
from apps.authentication.models import User
from apps.org_resources.models import Address
from IDBOOKAPI.basic_resources import (
    GENDER_CHOICES, KYC_DOCUMENT_CHOICES, LANGUAGES_CHOICES,
    CUSTOMER_GROUP, TXN_TYPE_CHOICES)


class Customer(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE,
                             related_name="customer_profile",
                             verbose_name="customer_profile",
                             help_text="user profile in user table")
    added_user = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name="customer_profiles", null=True,blank=True,
                                   help_text="Confirmed / Added User")
    address = models.TextField(null=True, blank=True,
                               help_text="Full address", verbose_name="customer_address")
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, null=True, blank=True,
                              help_text="Select the gender of the customer."
                              )
    date_of_birth = models.DateField(null=True, blank=True,
                                     help_text="Enter the date of birth of the customer.")
    profile_picture = models.FileField(upload_to='customer/profile/', blank=True, null=True)
    id_proof_type = models.CharField(max_length=20, choices=KYC_DOCUMENT_CHOICES,
                                     blank=True, null=True,)
    # id_proof = models.URLField(default='')
    id_proof = models.FileField(upload_to='customer/idproof/', blank=True, null=True)
    pan_card = models.FileField(upload_to='customer/idproof/', blank=True, null=True)
    pan_card_number = models.CharField(max_length=20, blank=True, null=True,)
    aadhar_card = models.FileField(upload_to='customer/idproof/', blank=True, null=True)
    aadhar_card_number = models.CharField(max_length=20, blank=True, null=True,)

    loyalty_points = models.PositiveIntegerField(default=0, help_text="Total loyalty points earned by the customer.")
    membership_status = models.BooleanField(default=False, help_text="Check if the customer has a membership.")
    emergency_contact_name = models.CharField(max_length=100, blank=True, null=True,
                                              help_text="Name of the customer's emergency contact person.")
    emergency_contact_phone = models.CharField(max_length=10, blank=True, null=True,
                                               help_text="Phone number of the customer's emergency contact.")
    preferred_language = models.CharField(max_length=20, null=True, blank=True, choices=LANGUAGES_CHOICES,
                                          help_text="Preferred language of communication for the customer.")
    dietary_restrictions = models.TextField(blank=True, null=True,
                                            help_text="Any dietary restrictions or preferences for the customer.")
    special_requests = models.TextField(blank=True, null=True,
                                        help_text="Any special requests or notes from the customer.")

    group_name = models.CharField(max_length=10, default='DEFAULT', choices=CUSTOMER_GROUP,
                                          help_text="Group for the customer.")
    employee_id = models.CharField(max_length=20, null=True, blank=True)
    department = models.CharField(max_length=30, null=True, blank=True)

    privileged = models.BooleanField(default=False, help_text="Whether the customer is privileged.")
    active = models.BooleanField(default=False, help_text="Whether the customer is active.")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.email}"

class Wallet(models.Model):
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_user')
    balance = models.FloatField(default=0, blank=True, null=True)

    active = models.BooleanField(default=True)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)

class WalletTransaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='wallet_transactions')
    amount = models.FloatField()
    transaction_type = models.CharField(max_length=10, choices=TXN_TYPE_CHOICES,
                                        help_text="Credit / Debit")
    transaction_id = models.CharField(max_length=350, null=True, blank=True, help_text="transaction id")
    transaction_details = models.TextField(help_text="Transaction description")
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return str(self.user.email)
    
