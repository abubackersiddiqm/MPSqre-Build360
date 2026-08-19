from django.db import migrations
from django.db.backends.base.schema import BaseDatabaseSchemaEditor
from django.db.migrations.state import StateApps


def create_audit_guard(
    apps: StateApps,
    schema_editor: BaseDatabaseSchemaEditor,
) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        CREATE OR REPLACE FUNCTION build360_reject_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'platform_audit_event is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    schema_editor.execute(
        """
        CREATE TRIGGER platform_audit_event_append_only
        BEFORE UPDATE OR DELETE ON platform_audit_event
        FOR EACH ROW EXECUTE FUNCTION build360_reject_audit_mutation();
        """
    )


def remove_audit_guard(
    apps: StateApps,
    schema_editor: BaseDatabaseSchemaEditor,
) -> None:
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(
        """
        DROP TRIGGER IF EXISTS platform_audit_event_append_only
        ON platform_audit_event;
        """
    )
    schema_editor.execute(
        "DROP FUNCTION IF EXISTS build360_reject_audit_mutation();"
    )


class Migration(migrations.Migration):
    dependencies = [
        ("build360_platform", "0002_auditevent"),
    ]

    operations = [
        migrations.RunPython(create_audit_guard, remove_audit_guard),
    ]

