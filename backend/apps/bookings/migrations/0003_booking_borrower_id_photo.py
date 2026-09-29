from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bookings', '0002_remove_booking_return_time_booking_payment_date_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='booking',
            name='borrower_id_photo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='booking_request_ids/',
                help_text='Borrower ID photo submitted with booking request',
            ),
        ),
    ]
