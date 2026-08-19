import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Normalize the historical migration state for WBSNode.parent.

    Phase 30's initial migration serialized the self-relation as ``to='self'``.
    The live model deconstructs that relation as ``to='workops.wbsnode'``, which
    causes ``makemigrations --check --dry-run`` to report a persistent AlterField
    even though the physical database relationship is already the same self-FK.

    This is intentionally a STATE-ONLY migration: it updates Django's migration
    state without altering the existing database column or foreign-key constraint.
    """

    dependencies = [
        ("workops", "0003_grant_existing_admin_roles"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name="wbsnode",
                    name="parent",
                    field=models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="workops.wbsnode",
                    ),
                ),
            ],
        ),
    ]
