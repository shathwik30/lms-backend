from django.urls import path

from . import views

app_name = "exams"

urlpatterns = [
    # Student
    path("<int:pk>/", views.ExamDetailView.as_view(), name="exam-detail"),
    path("<int:pk>/start/", views.ExamStartView.as_view(), name="exam-start"),
    path("attempts/<int:pk>/submit/", views.ExamSubmitView.as_view(), name="exam-submit"),
    path("attempts/<int:pk>/result/", views.AttemptResultView.as_view(), name="attempt-result"),
    path("attempts/<int:pk>/violations/", views.AttemptViolationsView.as_view(), name="attempt-violations"),
    path("attempts/<int:pk>/report-violation/", views.ReportViolationView.as_view(), name="report-violation"),
    path("attempts/", views.StudentAttemptListView.as_view(), name="student-attempts"),
    # Admin
    path("admin/questions/", views.AdminQuestionListCreateView.as_view(), name="admin-question-list"),
    path("admin/questions/<int:pk>/", views.AdminQuestionDetailView.as_view(), name="admin-question-detail"),
    path(
        "admin/questions/<int:question_pk>/options/",
        views.AdminOptionListCreateView.as_view(),
        name="admin-option-list",
    ),
    path("admin/", views.AdminExamListCreateView.as_view(), name="admin-exam-list"),
    path("admin/<int:pk>/", views.AdminExamDetailView.as_view(), name="admin-exam-detail"),
    path("admin/attempts/", views.AdminAttemptListView.as_view(), name="admin-attempt-list"),
    path("admin/options/<int:pk>/", views.AdminOptionDetailView.as_view(), name="admin-option-detail"),
]
