from django.contrib import admin

from resources.models import ResourceProvision


@admin.register(ResourceProvision)
class ResourceProvisionAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "cluster",
        "namespace_name",
        "service_account_name",
        "status",
        "updated_at",
    )
    list_filter = ("status", "cluster")
    search_fields = (
        "user__username",
        "namespace_name",
        "service_account_name",
        "keycloak_sub",
    )
    readonly_fields = ("created_at", "updated_at")
