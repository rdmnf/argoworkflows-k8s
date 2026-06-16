from django.conf import settings
from django.db import models


class WorkflowScript(models.Model):
    """User-authored Argo Workflow manifest stored in the portal."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        READY = "ready", "Ready"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workflow_scripts",
    )
    cluster = models.ForeignKey(
        "clusters.K8sCluster",
        on_delete=models.CASCADE,
        related_name="workflow_scripts",
    )
    subject = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    namespace_name = models.CharField(
        max_length=253,
        blank=True,
        help_text="Target namespace on the cluster (from the user's provision).",
    )
    manifest = models.TextField(
        help_text="Argo Workflow YAML manifest.",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        verbose_name = "workflow script"
        verbose_name_plural = "workflow scripts"

    def __str__(self) -> str:
        return f"{self.subject} ({self.user})"

    @property
    def manifest_preview(self) -> str:
        text = self.manifest.strip()
        if len(text) <= 120:
            return text
        return f"{text[:117]}..."

    @property
    def latest_run(self):
        return self.runs.order_by("-submitted_at").first()


class WorkflowRun(models.Model):
    """A submission of a workflow script to the Kubernetes API."""

    class Status(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        FAILED = "failed", "Failed"

    workflow = models.ForeignKey(
        WorkflowScript,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="workflow_runs",
    )
    cluster = models.ForeignKey(
        "clusters.K8sCluster",
        on_delete=models.CASCADE,
        related_name="workflow_runs",
    )
    status = models.CharField(max_length=20, choices=Status.choices)
    namespace_name = models.CharField(max_length=253)
    service_account_name = models.CharField(max_length=253, blank=True)
    k8s_workflow_name = models.CharField(max_length=253, blank=True)
    error_message = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        label = self.k8s_workflow_name or "failed run"
        return f"{self.workflow.subject} → {label}"
