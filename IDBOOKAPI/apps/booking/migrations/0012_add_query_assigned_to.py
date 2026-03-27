from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("booking", "0011_add_query_guest_access_token"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="query",
            name="assigned_to",
            field=models.ForeignKey(
                blank=True,
                help_text="Business user currently assigned to handle this query",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="queries_assigned",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

