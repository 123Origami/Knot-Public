from django.db import migrations, models


def disable_existing_payments(apps, schema_editor):
    SiteSettings = apps.get_model('core', 'SiteSettings')
    SiteSettings.objects.update(enable_payments=False)


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='sitesettings',
            name='enable_payments',
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(disable_existing_payments, noop),
    ]
