from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    """Extended user information synced from Keycloak on each login."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    keycloak_sub = models.CharField(max_length=255, unique=True, blank=True)
    preferred_username = models.CharField(max_length=150, blank=True)
    email_verified = models.BooleanField(default=False)
    keycloak_groups = models.JSONField(default=list, blank=True)
    last_oidc_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self) -> str:
        return self.preferred_username or self.user.get_username()
