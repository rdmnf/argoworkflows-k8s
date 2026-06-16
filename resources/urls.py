from django.urls import path

from resources import views

app_name = "resources"

urlpatterns = [
    path("my-resources/", views.my_resources, name="my_resources"),
    path("my-resources/<int:pk>/verify/", views.verify_provision, name="verify_provision"),
    path(
        "control/provisions/<int:pk>/verify/",
        views.admin_verify_provision,
        name="admin_verify_provision",
    ),
]
