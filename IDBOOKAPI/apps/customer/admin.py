from django.contrib import admin
from django import forms
from .models import Customer, Wallet, WalletTransaction


class WalletAdminForm(forms.ModelForm):
    class Meta:
        model = Wallet
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "user" in self.fields:
            self.fields["user"].required = False
        if "company" in self.fields:
            self.fields["company"].required = False


class WalletTransactionAdminForm(forms.ModelForm):
    class Meta:
        model = WalletTransaction
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "user" in self.fields:
            self.fields["user"].required = False
        if "company" in self.fields:
            self.fields["company"].required = False
        if "other_details" in self.fields:
            self.fields["other_details"].required = False


class WalletAdmin(admin.ModelAdmin):
    list_display = ("user", "company")
    form = WalletAdminForm
    # search_fields = ('company_name', 'company_phone', 'company_email', 'district', 'state', 'country', 'pin_code')
    # list_filter = ('state', 'country')


class WalletTransactionAdmin(admin.ModelAdmin):
    list_display = ("user", "company", "agent", "amount", "status", "created")
    form = WalletTransactionAdminForm


# Register your models here.
admin.site.register(Customer)
admin.site.register(Wallet, WalletAdmin)
admin.site.register(WalletTransaction, WalletTransactionAdmin)
