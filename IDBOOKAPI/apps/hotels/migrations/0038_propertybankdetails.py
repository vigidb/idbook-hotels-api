# Generated by Django 4.2.3 on 2024-12-10 08:42

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0037_delete_review'),
    ]

    operations = [
        migrations.CreateModel(
            name='PropertyBankDetails',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('account_number', models.CharField(max_length=35)),
                ('ifsc', models.CharField(max_length=25)),
                ('bank_name', models.CharField(max_length=35)),
                ('gstin', models.CharField(blank=True, default='', max_length=25)),
                ('pan', models.CharField(blank=True, default='', max_length=25)),
                ('tan', models.CharField(blank=True, default='', max_length=25)),
                ('active', models.BooleanField(default=True)),
                ('created', models.DateTimeField(auto_now_add=True)),
                ('updated', models.DateTimeField(auto_now=True)),
                ('property', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='property_bank', to='hotels.property')),
            ],
        ),
    ]
