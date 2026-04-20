from django.urls import path

from . import views

app_name = "exams"

urlpatterns = [
    # Student
    path("<uuid:pk>/", views.ExamDetailView.as_view(), name="exam-detail"),
    path("<uuid:pk>/start/", views.ExamStartView.as_view(), name="exam-start"),
    path("attempts/<uuid:pk>/submit/", views.ExamSubmitView.as_view(), name="exam-submit"),
    path("attempts/<uuid:pk>/result/", views.AttemptResultView.as_view(), name="attempt-result"),
    path("attempts/<uuid:pk>/violations/", views.AttemptViolationsView.as_view(), name="attempt-violations"),
    path("attempts/<uuid:pk>/report-violation/", views.ReportViolationView.as_view(), name="report-violation"),
    path("attempts/", views.StudentAttemptListView.as_view(), name="student-attempts"),
    # Admin
    path("admin/questions/", views.AdminQuestionListCreateView.as_view(), name="admin-question-list"),
    path("admin/questions/bulk/", views.AdminBulkQuestionCreateView.as_view(), name="admin-question-bulk-create"),
    path("admin/questions/<uuid:pk>/", views.AdminQuestionDetailView.as_view(), name="admin-question-detail"),
    path(
        "admin/questions/<uuid:question_pk>/options/",
        views.AdminOptionListCreateView.as_view(),
        name="admin-option-list",
    ),
    path("admin/", views.AdminExamListCreateView.as_view(), name="admin-exam-list"),
    path("admin/<uuid:pk>/", views.AdminExamDetailView.as_view(), name="admin-exam-detail"),
    path("admin/attempts/", views.AdminAttemptListView.as_view(), name="admin-attempt-list"),
    path("admin/<uuid:exam_pk>/stats/", views.AdminExamStatsView.as_view(), name="admin-exam-stats"),
    path("admin/options/<uuid:pk>/", views.AdminOptionDetailView.as_view(), name="admin-option-detail"),
]
