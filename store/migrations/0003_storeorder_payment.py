from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0002_product_is_visible'),
    ]

    operations = [
        migrations.AddField(
            model_name='storeorder',
            name='payment_status',
            field=models.CharField(
                choices=[('pending', 'Pending'), ('paid', 'Paid'), ('refunded', 'Refunded')],
                default='paid',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='storeorder',
            name='payment_method',
            field=models.CharField(blank=True, default='', max_length=50),
        ),
    ]
