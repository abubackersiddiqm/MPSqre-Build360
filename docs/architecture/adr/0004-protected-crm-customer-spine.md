# ADR-004 — Protected CRM customer spine

## Status

Accepted for Build360 0.4.0.

## Decision

Build360 CRM remains inside the modular monolith as an isolated bounded context. Every CRM aggregate is tenant-owned and resolved only through authenticated tenant context.

Contact endpoints are stored as authenticated ciphertext. Search and duplicate detection use purpose-bound HMAC blind indexes. Ordinary serializers never return raw protected values. A separate permission and mandatory reason code govern reveal operations, which append immutable audit evidence.

Lead and opportunity pipelines are configured through tenant-owned stages. Transitions use allow-listed next-stage codes and optimistic aggregate versions. Lead conversion locks the source lead and creates one immutable conversion snapshot linking the customer and opportunity.

## Consequences

- Encryption keys must be supplied independently of database storage.
- Key rotation is supported by ordered Fernet key lists.
- Pipeline setup is explicit per company.
- Conversion and transition APIs reject stale versions.
- Communication providers remain outside CRM and will be integrated through the later Communication Engine.
