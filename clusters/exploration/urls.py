from django.urls import path

from clusters.exploration import views

urlpatterns = [
    path("", views.cluster_explore, name="cluster_explore"),
]
