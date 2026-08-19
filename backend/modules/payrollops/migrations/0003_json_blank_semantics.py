from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payrollops", "0002_seed_permissions"),
    ]

    operations = [
        migrations.AlterField(
            model_name="paycomponentdefinition",
            name="configuration",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="compensationassignment",
            name="configuration",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="payrollperiod",
            name="configuration",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="payrollrun",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="payrollrunline",
            name="exception_codes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="payrollrunline",
            name="component_breakdown",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.AlterField(
            model_name="payrollrunline",
            name="calculation_trace",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="payrollexception",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="payrollapproval",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name="payrollexportbatch",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
