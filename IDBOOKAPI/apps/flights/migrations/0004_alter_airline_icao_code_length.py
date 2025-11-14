from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('flights', '0003_alter_airline_code_non_unique'),
    ]

    operations = [
        migrations.AlterField(
            model_name='airline',
            name='icao_code',
            field=models.CharField(
                max_length=10,
                blank=True,
                help_text='3-letter ICAO airline code (OpenFlights may contain some longer values)',
            ),
        ),
    ]
