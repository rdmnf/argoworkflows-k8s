from django.contrib import admin

from workflows.models import WorkflowRun, WorkflowScript


@admin.register(WorkflowScript)
class WorkflowScriptAdmin(admin.ModelAdmin):
    list_display = ("subject", "user", "cluster", "namespace_name", "status", "updated_at")
    list_filter = ("status", "cluster")
    search_fields = ("subject", "description", "user__username", "namespace_name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WorkflowRun)
class WorkflowRunAdmin(admin.ModelAdmin):
    list_display = (
        "workflow",
        "user",
        "status",
        "k8s_workflow_name",
        "namespace_name",
        "submitted_at",
    )
    list_filter = ("status", "cluster")
    search_fields = ("k8s_workflow_name", "workflow__subject", "user__username")
    readonly_fields = ("submitted_at",)
