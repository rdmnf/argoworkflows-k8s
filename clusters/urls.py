from django.urls import include, path

from clusters import views

app_name = "clusters"

urlpatterns = [
    path("", views.cluster_list, name="cluster_list"),
    path("<int:pk>/", include("clusters.exploration.urls")),
    path("<int:pk>/edit/", views.cluster_edit, name="cluster_edit"),
    path("<int:pk>/delete/", views.cluster_delete, name="cluster_delete"),
]
