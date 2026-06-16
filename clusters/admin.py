from django.contrib import admin

from clusters.models import K8sCluster


@admin.register(K8sCluster)
class K8sClusterAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "api_server_url",
        "default_namespace",
        "is_active",
        "created_by",
        "updated_at",
    )
    list_filter = ("is_active",)
    search_fields = ("name", "api_server_url", "description")
    readonly_fields = ("created_at", "updated_at", "created_by")
