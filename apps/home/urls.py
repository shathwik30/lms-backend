from django.urls import path

from . import views

app_name = "home"

urlpatterns = [
    # Public
    path("banners/", views.BannerListView.as_view(), name="banners"),
    path("featured/", views.FeaturedCoursesView.as_view(), name="featured"),
    path("levels/<uuid:level_id>/exams/", views.LevelExamsView.as_view(), name="level-exams"),
    # Admin
    path("admin/banners/", views.AdminBannerListCreateView.as_view(), name="admin-banner-list"),
    path("admin/banners/<uuid:pk>/", views.AdminBannerDetailView.as_view(), name="admin-banner-detail"),
]
