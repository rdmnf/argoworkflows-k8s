from django.conf import settings
from django.db import models

from resources.naming import ARGO_WORKFLOWS_ROLE_BINDING_NAME, ARGO_WORKFLOWS_ROLE_NAME


class ResourceProvision(models.Model):
    """Tracks a user's requested namespace and service account on a cluster."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        FAILED = "failed", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="resource_provisions",
    )
    cluster = models.ForeignKey(
        "clusters.K8sCluster",
        on_delete=models.CASCADE,
        related_name="resource_provisions",
    )
    keycloak_sub = models.CharField(max_length=255)
    namespace_name = models.CharField(max_length=253)
    service_account_name = models.CharField(max_length=253)
    service_account_token = models.TextField(blank=True)
    provision_steps = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "cluster"],
                name="unique_user_cluster_provision",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} @ {self.cluster.name} ({self.status})"

    @property
    def has_personal_token(self) -> bool:
        return bool(self.service_account_token.strip())

    @property
    def masked_token(self) -> str:
        token = self.service_account_token.strip()
        if len(token) <= 8:
            return "••••••••"
        return f"{'•' * 12}{token[-4:]}"

    @property
    def argo_workflows_role_name(self) -> str:
        return ARGO_WORKFLOWS_ROLE_NAME

    @property
    def argo_workflows_role_binding_name(self) -> str:
        return ARGO_WORKFLOWS_ROLE_BINDING_NAME

    @property
    def cluster_verified(self) -> bool:
        verify_keys = {
            "verify_namespace",
            "verify_service_account",
            "verify_role",
            "verify_role_binding",
        }
        steps = [s for s in self.provision_steps if s.get("key") in verify_keys]
        return bool(steps) and all(s.get("verified") for s in steps)
