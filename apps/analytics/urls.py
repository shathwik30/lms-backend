from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("revenue/", views.RevenueListView.as_view(), name="revenue"),
    path("levels/", views.LevelAnalyticsListView.as_view(), name="levels"),
    path("levels/<uuid:level_pk>/detail/", views.AdminLevelAnalyticsDetailView.as_view(), name="level-analytics-detail"),
    path("dashboard/", views.AdminDashboardView.as_view(), name="dashboard"),
]
