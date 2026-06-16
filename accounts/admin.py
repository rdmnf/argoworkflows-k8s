from django.contrib import admin

from accounts.models import UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "preferred_username",
        "user",
        "display_groups",
        "email_verified",
        "last_oidc_login",
        "updated_at",
    )
    search_fields = ("preferred_username", "user__username", "user__email", "keycloak_sub")
    readonly_fields = ("created_at", "updated_at", "last_oidc_login", "keycloak_groups")

    @admin.display(description="Groups")
    def display_groups(self, obj):
        return ", ".join(obj.keycloak_groups) if obj.keycloak_groups else "—"
