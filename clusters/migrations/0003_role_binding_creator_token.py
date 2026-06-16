from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clusters", "0002_split_cluster_tokens"),
    ]

    operations = [
        migrations.AddField(
            model_name="k8scluster",
            name="role_binding_creator_token",
            field=models.TextField(
                blank=True,
                help_text="Service account token with permission to create roles and role bindings in user namespaces.",
                verbose_name="Token for creating roles and role bindings",
            ),
        ),
    ]
