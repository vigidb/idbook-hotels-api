from django.contrib import admin
from .models import (
    Customer, Wallet, WalletTransaction)

# Register your models here.
admin.site.register(Customer)
admin.site.register(Wallet)
admin.site.register(WalletTransaction)
