# Generated by Django 4.2.3 on 2024-11-26 07:26

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('hotels', '0033_favoritelist'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='property',
            name='active',
        ),
        migrations.AddField(
            model_name='property',
            name='current_page',
            field=models.PositiveIntegerField(default=0, help_text='Pages completed for property in Front End'),
        ),
        migrations.AddField(
            model_name='property',
            name='status',
            field=models.CharField(choices=[('Active', 'Active'), ('In-Active', 'In-Active'), ('In-Progress', 'In-Progress'), ('Completed', 'Completed')], default='In-Progress', max_length=50),
        ),
    ]
