import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clusters", "0003_role_binding_creator_token"),
        ("workflows", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("namespace_name", models.CharField(max_length=253)),
                ("service_account_name", models.CharField(blank=True, max_length=253)),
                ("k8s_workflow_name", models.CharField(blank=True, max_length=253)),
                ("error_message", models.TextField(blank=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("submitted", "Submitted"), ("failed", "Failed")],
                        max_length=20,
                    ),
                ),
                ("submitted_at", models.DateTimeField(auto_now_add=True)),
                (
                    "cluster",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_runs",
                        to="clusters.k8scluster",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_runs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "workflow",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="runs",
                        to="workflows.workflowscript",
                    ),
                ),
            ],
            options={
                "ordering": ["-submitted_at"],
            },
        ),
    ]
