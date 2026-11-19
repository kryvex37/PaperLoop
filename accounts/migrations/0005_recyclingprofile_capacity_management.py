from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_backfill_organization_profiles"),
    ]

    operations = [
        migrations.AddField(
            model_name="recyclingprofile",
            name="maximum_capacity",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
        migrations.AddField(
            model_name="recyclingprofile",
            name="current_allocated_load",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="recyclingprofile",
            name="capacity_unit",
            field=models.CharField(choices=[("kg", "Kilograms"), ("ton", "Metric tons")], default="kg", max_length=8),
        ),
        migrations.AddField(
            model_name="recyclingprofile",
            name="capacity_period",
            field=models.CharField(choices=[("day", "per day"), ("week", "per week"), ("month", "per month")], default="month", max_length=8),
        ),
        migrations.RunSQL(
            sql="UPDATE accounts_recyclingprofile SET maximum_capacity = capacity_kg_per_month WHERE capacity_kg_per_month IS NOT NULL",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.AddConstraint(
            model_name="recyclingprofile",
            constraint=models.CheckConstraint(
                condition=models.Q(maximum_capacity__isnull=True) | models.Q(current_allocated_load__lte=models.F("maximum_capacity")),
                name="recycler_allocated_within_capacity",
            ),
        ),
    ]
