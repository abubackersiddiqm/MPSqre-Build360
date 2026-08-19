# Phase 11 — Governed AI foundations

## Scope

Phase 11 adds a tenant-owned AI governance boundary. It does not activate an
external AI provider and it does not permit autonomous business mutations.
The native Windows/no-Docker profile uses the deterministic
`local_grounded` adapter for validation and controlled demonstrations.

## Core controls

- Provider profiles store secret references, never provider secrets.
- Effective-dated model policies bound purpose, sources, classifications,
  context size, output size, retention, citation requirements, and tools.
- Retrieval is re-authorized for the current company and membership before
  every interaction.
- Raw prompts are represented by a SHA-256 digest and a bounded excerpt.
- Material response claims are linked to tenant-safe citations.
- Extraction input is not persisted; only a digest, requested schema,
  extracted values, confidence evidence, and human corrections are retained.
- Risk signals are advisory and cannot change source business records.
- Tool actions are proposals only and require an independent human decision.
- Phase 11 contains no executor for finance, contracts, safety, access,
  deletion, communications, or workflow transitions.
- Evaluation runs record guardrail evidence against the effective policy.

## API boundary

All endpoints require authentication, an active company membership, and the
semantic permission indicated by the operation.

- `GET /api/v1/ai/summary`
- `GET /api/v1/ai/providers`
- `GET|POST /api/v1/ai/policies`
- `GET|POST /api/v1/ai/interactions`
- `POST /api/v1/ai/interactions/{public_id}/review`
- `GET|POST /api/v1/ai/extractions`
- `POST /api/v1/ai/extractions/{public_id}/review`
- `GET|POST /api/v1/ai/risks`
- `POST /api/v1/ai/risks/{public_id}/decision`
- `GET|POST /api/v1/ai/actions`
- `POST /api/v1/ai/actions/{public_id}/decision`
- `GET|POST /api/v1/ai/evaluations`

## Local adapter behavior

The local adapter reads only governed reporting metrics authorized for the
current membership. It creates deterministic summaries with citations, parses
explicit `field: value` extraction input, and detects advisory risks from
approved metrics. It has no network access and does not execute tool actions.

## Production activation requirements

Before activating an external provider, approve and validate:

1. Provider contract, data residency, retention, and training-use terms.
2. Secret-manager integration and provider-specific adapter conformance.
3. Prompt-injection, tenant-leakage, grounding, citation, and tool-safety tests.
4. Jurisdiction-specific privacy and cross-border processing requirements.
5. Evaluation thresholds, kill switch, cost limits, and incident runbooks.
