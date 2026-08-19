# ADR 0011: Project delivery spine

## Status

Accepted for Phase 5.

## Decision

Projects, Design and Estimation are separate bounded contexts in the modular monolith. They share only public identifiers and the company-owned `DeliveryStage` lifecycle primitive from the Projects context.

- Tenant ownership leads every business query and compound index.
- Project, task, design-version and estimate-version statuses are data, not hardcoded authorization rules.
- Aggregate transitions use optimistic versions.
- Approved project and estimate baselines are append-only snapshots.
- Design versions preserve revision lineage and transmittals reference exact issued versions.
- BOQ money uses fixed-precision decimals; floating-point values are prohibited.
- Material mutations append audit and transactional outbox evidence.

## Consequences

The delivery spine can evolve without CRM writing directly into project tables. Regional scheduling, resource loading, procurement integration and finance posting remain later bounded-context integrations.
