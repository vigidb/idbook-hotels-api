# Generated by Django 4.2.3 on 2023-07-14 13:11

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('org_resources', '0003_roomtype'),
        ('hotels', '0002_review_delete_reviews'),
    ]

    operations = [
        migrations.AlterField(
            model_name='gallery',
            name='image_type',
            field=models.CharField(choices=[('DELUXE ROOM', 'DELUXE'), ('CLASSIC ROOM', 'CLASSIC'), ('PREMIUM ROOM', 'PREMIUM'), ('HOTEL', 'HOTEL'), ('BATHROOM', 'BATHROOM'), ('SURROUNDING', 'SURROUNDING')], max_length=25),
        ),
        migrations.AlterField(
            model_name='gallery',
            name='upload_image',
            field=models.CharField(max_length=255),
        ),
        migrations.AlterField(
            model_name='hotel',
            name='area_name',
            field=models.CharField(help_text='Area Name', max_length=60),
        ),
        migrations.AlterField(
            model_name='hotel',
            name='city_name',
            field=models.CharField(help_text='City Name', max_length=35),
        ),
        migrations.AlterField(
            model_name='hotel',
            name='description',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='hotel',
            name='district',
            field=models.CharField(max_length=20),
        ),
        migrations.AlterField(
            model_name='hotel',
            name='email',
            field=models.EmailField(max_length=254),
        ),
        migrations.AlterField(
            model_name='hotel',
            name='full_address',
            field=models.CharField(max_length=100),
        ),
        migrations.AlterField(
            model_name='hotel',
            name='location',
            field=models.CharField(help_text='Google map URL', max_length=255),
        ),
        migrations.AlterField(
            model_name='hotel',
            name='pin_code',
            field=models.PositiveIntegerField(),
        ),
        migrations.AlterField(
            model_name='review',
            name='body',
            field=models.TextField(),
        ),
        migrations.AlterField(
            model_name='review',
            name='email',
            field=models.EmailField(max_length=254),
        ),
        migrations.AlterField(
            model_name='room',
            name='amenities',
            field=models.ManyToManyField(related_name='rooms_amenities', to='org_resources.amenity'),
        ),
    ]
