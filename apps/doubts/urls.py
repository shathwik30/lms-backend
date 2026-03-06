from django.urls import path

from . import views

app_name = "doubts"

urlpatterns = [
    # Student
    path("", views.StudentDoubtListCreateView.as_view(), name="student-list"),
    path("<int:pk>/", views.StudentDoubtDetailView.as_view(), name="student-detail"),
    path("<int:pk>/reply/", views.StudentDoubtReplyView.as_view(), name="student-reply"),
    # Admin
    path("admin/", views.AdminDoubtListView.as_view(), name="admin-list"),
    path("admin/<int:pk>/", views.AdminDoubtDetailView.as_view(), name="admin-detail"),
    path("admin/<int:pk>/reply/", views.AdminDoubtReplyView.as_view(), name="admin-reply"),
    path("admin/<int:pk>/assign/", views.AdminAssignDoubtView.as_view(), name="admin-assign"),
    path("admin/<int:pk>/status/", views.AdminDoubtStatusView.as_view(), name="admin-status"),
    path("admin/<int:pk>/bonus/", views.AdminBonusMarksView.as_view(), name="admin-bonus"),
]
