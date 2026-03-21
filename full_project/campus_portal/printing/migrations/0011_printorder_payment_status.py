from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('printing', '0010_printorder_order_number'),
    ]

    operations = [
        migrations.AddField(
            model_name='printorder',
            name='estimated_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=8),
        ),
        migrations.AlterField(
            model_name='printorder',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending_payment', 'Pending Payment'),
                    ('paid', 'Paid'),
                    ('printing', 'Printing'),
                    ('collected', 'Collected'),
                ],
                default='paid',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='printorder',
            name='order_number',
            field=models.CharField(blank=True, max_length=50, unique=True),
        ),
    ]
