from django.urls import path

from workflows import views

app_name = "workflows"

urlpatterns = [
    path("my-workflows/", views.my_workflows, name="my_workflows"),
    path("my-workflows/<int:pk>/", views.workflow_detail, name="workflow_detail"),
    path("my-workflows/<int:pk>/edit/", views.workflow_edit, name="workflow_edit"),
    path("my-workflows/<int:pk>/delete/", views.workflow_delete, name="workflow_delete"),
    path("my-workflows/<int:pk>/submit/", views.workflow_submit, name="workflow_submit"),
    path("control/workflows/", views.admin_workflows, name="admin_workflows"),
    path(
        "control/workflows/<int:pk>/",
        views.admin_workflow_detail,
        name="admin_workflow_detail",
    ),
]
