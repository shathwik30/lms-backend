from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    # Student
    path("initiate/", views.InitiatePaymentView.as_view(), name="initiate"),
    path("verify/", views.VerifyPaymentView.as_view(), name="verify"),
    path("dev-purchase/", views.DevPurchaseView.as_view(), name="dev-purchase"),
    path("preview/<uuid:level_id>/", views.LevelPurchasePreviewView.as_view(), name="level-purchase-preview"),
    path("purchases/", views.PurchaseHistoryView.as_view(), name="purchase-history"),
    path("purchases/<uuid:pk>/", views.PurchaseDetailView.as_view(), name="purchase-detail"),
    path("transactions/", views.TransactionHistoryView.as_view(), name="transaction-history"),
    path("transactions/<uuid:pk>/", views.TransactionDetailView.as_view(), name="transaction-detail"),
    # Admin
    path("admin/dashboard/", views.AdminPaymentDashboardView.as_view(), name="admin-payment-dashboard"),
    path("admin/purchases/", views.AdminPurchaseListView.as_view(), name="admin-purchase-list"),
    path("admin/purchases/<uuid:pk>/", views.AdminPurchaseDetailView.as_view(), name="admin-purchase-detail"),
    path(
        "admin/transactions/<uuid:pk>/",
        views.AdminTransactionDetailView.as_view(),
        name="admin-transaction-detail",
    ),
    path("admin/extend/", views.AdminExtendValidityView.as_view(), name="admin-extend"),
]
