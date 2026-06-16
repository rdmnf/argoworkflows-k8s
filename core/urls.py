from django.urls import path

from core import views
from resources import views as resource_views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("profile/", views.profile, name="profile"),
    path("control/", views.admin_control, name="admin_control"),
    path("control/users/<int:user_id>/", resource_views.user_detail, name="admin_user_detail"),
]
