from django.urls import path

from apps.levels.views import AdminWeekDetailView, AdminWeekListCreateView

from . import views

app_name = "courses"

urlpatterns = [
    # Student
    path("level/<uuid:level_pk>/", views.LevelCourseView.as_view(), name="level-courses"),
    path("<uuid:course_pk>/sessions/", views.CourseCurriculumView.as_view(), name="course-sessions"),
    path("sessions/<uuid:pk>/", views.SessionDetailView.as_view(), name="session-detail"),
    path("sessions/<uuid:pk>/complete-resource/", views.CompleteResourceSessionView.as_view(), name="complete-resource"),
    path("bookmarks/", views.BookmarkListCreateView.as_view(), name="bookmark-list"),
    path("bookmarks/<uuid:pk>/", views.BookmarkDeleteView.as_view(), name="bookmark-delete"),
    # Admin
    path("admin/", views.AdminCourseListCreateView.as_view(), name="admin-course-list"),
    path("admin/<uuid:pk>/", views.AdminCourseDetailView.as_view(), name="admin-course-detail"),
    path("admin/<uuid:course_pk>/weeks/", AdminWeekListCreateView.as_view(), name="admin-week-list"),
    path("admin/weeks/<uuid:pk>/", AdminWeekDetailView.as_view(), name="admin-week-detail"),
    path("admin/sessions/", views.AdminSessionListCreateView.as_view(), name="admin-session-list"),
    path("admin/sessions/<uuid:pk>/", views.AdminSessionDetailView.as_view(), name="admin-session-detail"),
]
