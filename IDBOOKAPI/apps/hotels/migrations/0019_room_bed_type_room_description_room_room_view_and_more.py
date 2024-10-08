# Generated by Django 4.2.3 on 2024-02-01 04:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0018_remove_gallery_managed_by_rule'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='bed_type',
            field=models.CharField(choices=[('KING', 'KING'), ('QUEEN', 'QUEEN'), ('SINGLE', 'SINGLE')], default='KING', max_length=25),
        ),
        migrations.AddField(
            model_name='room',
            name='description',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='room',
            name='room_view',
            field=models.CharField(choices=[('SEA VIEW', 'DELUXE'), ('RIVER VIEW', 'CLASSIC'), ('VALLEY VIEW', 'PREMIUM')], default='', max_length=25),
        ),
        migrations.AlterField(
            model_name='room',
            name='room_type',
            field=models.CharField(choices=[('DELUXE', 'DELUXE'), ('CLASSIC', 'CLASSIC'), ('PREMIUM', 'PREMIUM')], default='DELUXE', max_length=25),
        ),
    ]
