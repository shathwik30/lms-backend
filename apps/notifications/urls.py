from django.urls import path

from . import views

app_name = "notifications"

urlpatterns = [
    path("", views.NotificationListView.as_view(), name="list"),
    path("<int:pk>/", views.NotificationDeleteView.as_view(), name="delete"),
    path("<int:pk>/read/", views.NotificationMarkReadView.as_view(), name="mark-read"),
    path("read-all/", views.NotificationMarkAllReadView.as_view(), name="mark-all-read"),
    path("clear-all/", views.NotificationDeleteAllView.as_view(), name="clear-all"),
    path("unread-count/", views.UnreadCountView.as_view(), name="unread-count"),
]
