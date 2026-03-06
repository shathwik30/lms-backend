from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import views

app_name = "users"

urlpatterns = [
    # Public
    path("register/", views.RegisterView.as_view(), name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("google/", views.GoogleAuthView.as_view(), name="google-auth"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("me/", views.MeView.as_view(), name="me"),
    path("change-password/", views.ChangePasswordView.as_view(), name="change-password"),
    path("password-reset/", views.PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password-reset/confirm/", views.PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("otp/send/", views.SendOTPView.as_view(), name="send-otp"),
    path("otp/verify/", views.VerifyOTPView.as_view(), name="verify-otp"),
    path("preferences/", views.UserPreferenceView.as_view(), name="preferences"),
    path("onboarding/complete/", views.CompleteOnboardingView.as_view(), name="complete-onboarding"),
    path("report-issue/", views.ReportIssueView.as_view(), name="report-issue"),
    path("my-issues/", views.IssueReportListView.as_view(), name="my-issues"),
    # Admin
    path("admin/students/", views.AdminStudentListView.as_view(), name="admin-student-list"),
    path("admin/students/<int:pk>/", views.AdminStudentDetailView.as_view(), name="admin-student-detail"),
]
