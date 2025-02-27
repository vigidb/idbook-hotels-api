# Generated by Django 4.2.3 on 2024-11-28 05:56

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0034_remove_property_active_property_current_page_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='property',
            name='property_type',
            field=models.CharField(choices=[('Hotel', 'Hotel'), ('Cottage', 'Cottage'), ('Villa', 'Villa'), ('Cabin', 'Cabin'), ('Farmstay', 'Farmstay'), ('Houseboat', 'Houseboat'), ('Lighthouse', 'Lighthouse')], default='Hotel', max_length=50),
        ),
        migrations.AddField(
            model_name='property',
            name='rental_form',
            field=models.CharField(choices=[('entire place', 'entire place'), ('private room', 'private room'), ('share room', 'share room')], default='Private room', max_length=50),
        ),
        migrations.AddField(
            model_name='room',
            name='is_slot_price_enabled',
            field=models.BooleanField(default=False),
        ),
    ]
