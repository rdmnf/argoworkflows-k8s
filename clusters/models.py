from django.conf import settings
from django.db import models


def _mask_token(token: str) -> str:
    token = token.strip()
    if len(token) <= 8:
        return "••••••••"
    return f"{'•' * 12}{token[-4:]}"


class K8sCluster(models.Model):
    """Kubernetes cluster credentials and metadata."""

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="k8s_clusters",
    )
    name = models.CharField(max_length=120)
    api_server_url = models.URLField(
        help_text="Kubernetes API server URL, e.g. https://192.168.1.10:6443",
    )
    namespace_creator_token = models.TextField(
        verbose_name="Token for creating namespaces",
        help_text="Service account token with permission to create namespaces.",
    )
    service_account_creator_token = models.TextField(
        verbose_name="Token for creating service accounts",
        help_text="Service account token with permission to create service accounts in user namespaces.",
        blank=True,
    )
    role_binding_creator_token = models.TextField(
        verbose_name="Token for creating roles and role bindings",
        help_text="Service account token with permission to create roles and role bindings in user namespaces.",
        blank=True,
    )
    ca_certificate = models.TextField(
        blank=True,
        help_text="Optional cluster CA certificate (PEM format).",
    )
    default_namespace = models.CharField(max_length=253, default="default")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Kubernetes cluster"
        verbose_name_plural = "Kubernetes clusters"

    def __str__(self) -> str:
        return self.name

    @property
    def masked_namespace_token(self) -> str:
        return _mask_token(self.namespace_creator_token)

    @property
    def masked_service_account_creator_token(self) -> str:
        return _mask_token(self.service_account_creator_token)

    @property
    def masked_role_binding_creator_token(self) -> str:
        return _mask_token(self.role_binding_creator_token)

    # Backwards compatibility for templates/code that used masked_token
    @property
    def masked_token(self) -> str:
        return self.masked_namespace_token
