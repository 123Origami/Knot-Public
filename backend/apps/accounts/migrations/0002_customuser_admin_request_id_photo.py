from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='admin_request_id_photo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='admin_request_ids/',
                help_text='Photo of government-issued ID submitted for admin request review',
            ),
        ),
    ]
