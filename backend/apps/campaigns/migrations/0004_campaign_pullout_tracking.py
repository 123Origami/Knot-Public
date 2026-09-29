from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("campaigns", "0003_alter_campaign_min_contribution"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="campaign",
            name="funds_pulled_out",
            field=models.BooleanField(
                default=False,
                help_text="Whether admin has completed pullout after funding goal is reached",
            ),
        ),
        migrations.AddField(
            model_name="campaign",
            name="pulled_out_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="campaign",
            name="pulled_out_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="campaign_pullouts",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
