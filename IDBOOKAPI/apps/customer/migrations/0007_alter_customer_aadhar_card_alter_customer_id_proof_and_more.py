# Generated by Django 4.2.3 on 2024-10-12 09:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('customer', '0006_alter_customer_dietary_restrictions_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='customer',
            name='aadhar_card',
            field=models.FileField(blank=True, null=True, upload_to='customer/idproof/'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='id_proof',
            field=models.FileField(blank=True, null=True, upload_to='customer/idproof/'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='pan_card',
            field=models.FileField(blank=True, null=True, upload_to='customer/idproof/'),
        ),
        migrations.AlterField(
            model_name='customer',
            name='profile_picture',
            field=models.FileField(blank=True, null=True, upload_to='customer/profile/'),
        ),
    ]