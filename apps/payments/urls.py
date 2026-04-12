from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # Student
    path("initiate/", views.InitiatePaymentView.as_view(), name="initiate"),
    path("verify/", views.VerifyPaymentView.as_view(), name="verify"),
    path("dev-purchase/", views.DevPurchaseView.as_view(), name="dev-purchase"),
    path("preview/<int:level_id>/", views.LevelPurchasePreviewView.as_view(), name="level-purchase-preview"),
    path("purchases/", views.PurchaseHistoryView.as_view(), name="purchase-history"),
    path("transactions/", views.TransactionHistoryView.as_view(), name="transaction-history"),
    # Razorpay webhook (unauthenticated, signature-verified)
    path("webhook/razorpay/", views.RazorpayWebhookView.as_view(), name="razorpay-webhook"),
    # Admin
    path("admin/dashboard/", views.AdminPaymentDashboardView.as_view(), name="admin-payment-dashboard"),
    path("admin/purchases/", views.AdminPurchaseListView.as_view(), name="admin-purchase-list"),
    path("admin/extend/", views.AdminExtendValidityView.as_view(), name="admin-extend"),
]
