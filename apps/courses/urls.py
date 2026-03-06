from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    # Student
    path("level/<int:level_pk>/", views.LevelCourseView.as_view(), name="level-courses"),
    path("<int:course_pk>/sessions/", views.CourseSessionsView.as_view(), name="course-sessions"),
    path("sessions/<int:pk>/", views.SessionDetailView.as_view(), name="session-detail"),
    path("bookmarks/", views.BookmarkListCreateView.as_view(), name="bookmark-list"),
    path("bookmarks/<int:pk>/", views.BookmarkDeleteView.as_view(), name="bookmark-delete"),
    # Admin
    path("admin/", views.AdminCourseListCreateView.as_view(), name="admin-course-list"),
    path("admin/<int:pk>/", views.AdminCourseDetailView.as_view(), name="admin-course-detail"),
    path("admin/sessions/", views.AdminSessionListCreateView.as_view(), name="admin-session-list"),
    path("admin/sessions/<int:pk>/", views.AdminSessionDetailView.as_view(), name="admin-session-detail"),
    path("admin/resources/", views.AdminResourceListCreateView.as_view(), name="admin-resource-list"),
    path("admin/resources/<int:pk>/", views.AdminResourceDetailView.as_view(), name="admin-resource-detail"),
]
