from django.urls import path

from . import views

app_name = "feedback"

urlpatterns = [
    # Student
    path("sessions/<int:session_pk>/", views.SubmitFeedbackView.as_view(), name="submit"),
    path("", views.StudentFeedbackListView.as_view(), name="student-list"),
    # Admin
    path("admin/", views.AdminFeedbackListView.as_view(), name="admin-list"),
]
