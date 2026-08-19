# Repository instructions

The Product Bible v0.1 is authoritative. Every material change must cite stable
requirement IDs in its issue, design note, tests, or traceability record.

Preserve modular-monolith boundaries. A domain module owns its models,
application services, policies, API, events, migrations, and tests. Do not
mutate another module's tables directly.

Every tenant-owned query and command must resolve authenticated membership and
apply tenant scope before object lookup. Never treat a client-supplied company
identifier as authorization.

Never hardcode roles, workflow statuses, approval chains, tax rules,
currencies, providers, or subscription entitlements.

Use fixed-precision decimals for money and quantity, timezone-aware UTC
timestamps, object storage for file bytes, and append-only records for audit,
events, inventory movements, and posted financial facts.

Do not log secrets, raw tokens, protected contact values, provider credentials,
or private object-storage keys.

