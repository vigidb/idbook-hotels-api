from django.contrib import admin
from .models import (
    Customer, Wallet, WalletTransaction)

class WalletAdmin(admin.ModelAdmin):
    list_display = ('user', 'company')
    #search_fields = ('company_name', 'company_phone', 'company_email', 'district', 'state', 'country', 'pin_code')
    #list_filter = ('state', 'country')

# Register your models here.
admin.site.register(Customer)
admin.site.register(Wallet, WalletAdmin)
admin.site.register(WalletTransaction, WalletAdmin)
