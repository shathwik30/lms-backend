from django.urls import path

from . import views

app_name = "levels"

urlpatterns = [
    # Public
    path("", views.LevelListView.as_view(), name="level-list"),
    path("<int:pk>/", views.LevelDetailView.as_view(), name="level-detail"),
    # Admin
    path("admin/", views.AdminLevelListCreateView.as_view(), name="admin-level-list"),
    path("admin/<int:pk>/", views.AdminLevelDetailView.as_view(), name="admin-level-detail"),
    path("admin/<int:level_pk>/weeks/", views.AdminWeekListCreateView.as_view(), name="admin-week-list"),
    path("admin/weeks/<int:pk>/", views.AdminWeekDetailView.as_view(), name="admin-week-detail"),
]
