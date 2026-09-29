from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('items', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='itemsuggestion',
            name='image',
            field=models.ImageField(blank=True, help_text='Optional reference photo supplied by the member', null=True, upload_to='suggestion_images/'),
        ),
    ]
