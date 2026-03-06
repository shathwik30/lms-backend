from django.urls import path

from . import views

app_name = "certificates"

urlpatterns = [
    # Student
    path("", views.StudentCertificateListView.as_view(), name="list"),
    path("<int:pk>/", views.StudentCertificateDetailView.as_view(), name="detail"),
    # Admin
    path("admin/", views.AdminCertificateListView.as_view(), name="admin-list"),
]
