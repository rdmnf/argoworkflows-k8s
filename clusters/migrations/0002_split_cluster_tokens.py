from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("clusters", "0001_initial"),
    ]

    operations = [
        migrations.RenameField(
            model_name="k8scluster",
            old_name="service_account_token",
            new_name="namespace_creator_token",
        ),
        migrations.AlterField(
            model_name="k8scluster",
            name="namespace_creator_token",
            field=models.TextField(
                help_text="Service account token with permission to create namespaces.",
                verbose_name="Token for creating namespaces",
            ),
        ),
        migrations.AddField(
            model_name="k8scluster",
            name="service_account_creator_token",
            field=models.TextField(
                blank=True,
                help_text="Service account token with permission to create service accounts in user namespaces.",
                verbose_name="Token for creating service accounts",
            ),
        ),
    ]
