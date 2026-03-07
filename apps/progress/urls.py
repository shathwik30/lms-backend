from django.urls import path

from . import views

app_name = "progress"

urlpatterns = [
    # Student
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("sessions/<int:session_pk>/", views.UpdateSessionProgressView.as_view(), name="update-session"),
    path("levels/<int:level_pk>/sessions/", views.SessionProgressListView.as_view(), name="level-sessions"),
    path("levels/", views.LevelProgressListView.as_view(), name="level-progress"),
    path("courses/<int:course_pk>/", views.CourseProgressView.as_view(), name="course-progress"),
    path("levels/<int:level_pk>/courses/", views.LevelCourseProgressView.as_view(), name="level-course-progress"),
    path("calendar/", views.CalendarView.as_view(), name="calendar"),
    path("leaderboard/", views.LeaderboardView.as_view(), name="leaderboard"),
]
