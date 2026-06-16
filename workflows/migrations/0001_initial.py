import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("clusters", "0003_role_binding_creator_token"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkflowScript",
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
                ("subject", models.CharField(max_length=200)),
                ("description", models.TextField(blank=True)),
                (
                    "namespace_name",
                    models.CharField(
                        blank=True,
                        help_text="Target namespace on the cluster (from the user's provision).",
                        max_length=253,
                    ),
                ),
                (
                    "manifest",
                    models.TextField(help_text="Argo Workflow YAML manifest."),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[("draft", "Draft"), ("ready", "Ready")],
                        default="draft",
                        max_length=20,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "cluster",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_scripts",
                        to="clusters.k8scluster",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workflow_scripts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "workflow script",
                "verbose_name_plural": "workflow scripts",
                "ordering": ["-updated_at"],
            },
        ),
    ]
