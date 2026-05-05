from django.urls import path
from rest_framework import routers

from apps.customer.viewsets import (
    CustomerViewSet,
    WalletTransactionViewSet,
    WalletViewSet,
)
from apps.customer.wallet_admin_views import RejectPendingWalletRechargeView

router = routers.DefaultRouter()

router.register(r"customers", CustomerViewSet, basename="customers")
router.register(r"wallet", WalletViewSet, basename="wallet")
router.register(
    r"wallet-transaction", WalletTransactionViewSet, basename="wallet-transaction"
)

urlpatterns = [
    path(
        "wallet/pending-recharges/<int:pk>/reject/",
        RejectPendingWalletRechargeView.as_view(),
        name="wallet-pending-recharge-reject",
    ),
    # Explicit routes registered before the router so paths like
    # wallet/admin/wallets/ are never confused with wallet/<pk>/ and never hit
    # APPEND_SLASH redirects from a partial match.
    path(
        "wallet/recharge/fee-preview/",
        WalletViewSet.as_view({"get": "wallet_recharge_fee_preview"}),
        name="wallet-recharge-fee-preview-explicit",
    ),
    path(
        "wallet/admin/wallets/",
        WalletViewSet.as_view({"get": "admin_wallet_list"}),
        name="wallet-admin-list-explicit",
    ),
    path(
        "wallet/admin/summary/",
        WalletViewSet.as_view({"get": "admin_wallet_dashboard_summary"}),
        name="wallet-admin-dashboard-summary-explicit",
    ),
    path(
        "wallet/admin/funds-summary/",
        WalletViewSet.as_view({"get": "admin_wallet_funds_summary"}),
        name="wallet-admin-funds-summary-explicit",
    ),
    path(
        "wallet/<int:pk>/admin-summary/",
        WalletViewSet.as_view({"get": "admin_wallet_summary"}),
        name="wallet-admin-summary-explicit",
    ),
    path(
        "wallet/<int:pk>/admin/",
        WalletViewSet.as_view({"patch": "admin_wallet_manage", "delete": "admin_wallet_manage"}),
        name="wallet-admin-manage-explicit",
    ),
    path(
        "wallet-transaction/admin/transactions/",
        WalletTransactionViewSet.as_view({"get": "admin_all_transactions"}),
        name="wallet-transaction-admin-all-explicit",
    ),
    path(
        "wallet-transaction/admin/stats/",
        WalletTransactionViewSet.as_view({"get": "admin_transactions_stats"}),
        name="wallet-transaction-admin-stats-explicit",
    ),
] + router.urls
