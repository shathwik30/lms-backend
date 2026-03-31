from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # Student
    path("initiate/", views.InitiatePaymentView.as_view(), name="initiate"),
    path("verify/", views.VerifyPaymentView.as_view(), name="verify"),
    path("purchases/", views.PurchaseHistoryView.as_view(), name="purchase-history"),
    path("transactions/", views.TransactionHistoryView.as_view(), name="transaction-history"),
    # Admin
    path("admin/dashboard/", views.AdminPaymentDashboardView.as_view(), name="admin-payment-dashboard"),
    path("admin/purchases/", views.AdminPurchaseListView.as_view(), name="admin-purchase-list"),
    path("admin/extend/", views.AdminExtendValidityView.as_view(), name="admin-extend"),
]
