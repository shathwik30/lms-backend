from django.urls import path

from . import views

app_name = "analytics"

urlpatterns = [
    path("revenue/", views.RevenueListView.as_view(), name="revenue"),
    path("levels/", views.LevelAnalyticsListView.as_view(), name="levels"),
]
