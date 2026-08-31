from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("booking", "0008_merge_20260224_1042"),
    ]

    operations = [
        migrations.AddField(
            model_name="query",
            name="agent",
            field=models.ForeignKey(
                to="org_resources.agentdetail",
                on_delete=models.SET_NULL,
                null=True,
                blank=True,
                related_name="queries",
                help_text="Agent associated with this query (if created/managed by agent)",
            ),
        ),
    ]

