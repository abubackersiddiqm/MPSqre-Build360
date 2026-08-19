# CRM Lead Intelligence Foundation v0.45.2.17 — Traceability

Stable change IDs for this controlled increment:

- **CRM-LI-001** — Enrich existing protected Contact with address, source, tags, notes, custom fields and owner reference without duplicating contact storage.
- **CRM-LI-002** — Expand existing CRM Activity types to Call, WhatsApp, SMS, Email, Meeting, Follow-up, Note, Voice Note, Document, Photo, Video, Task, Status Change and Assignment Change.
- **CRM-LI-003** — Provide a chronological Lead Log Book over existing Activity, StageHistory and ConversionSnapshot records.
- **CRM-LI-004** — Attach governed Files to CRM Activity through a CRM-owned reference; bytes remain in Files/object storage and downloads remain scan-gated.
- **CRM-LI-005** — Provide company Activity cockpit metrics and filterable activity list.
- **CRM-LI-006** — Enrich lead cards with source, owner, last activity, next activity and activity count.
- **CRM-LI-007** — Preserve protected phone/email reveal auditing for Call/WhatsApp quick actions.
- **CRM-LI-008** — Every new CRM query/command is tenant scoped; cross-tenant activity/file attachment is rejected.
- **CRM-LI-009** — Do not implement Meta Ads ingestion or AI summaries/recommendations in this increment; those require separate governed follow-on changes.
- **CRM-LI-010** — Existing conversion remains idempotent and the Log Book renders conversion/stage evidence instead of creating duplicate history tables.

Source: user-approved CRM / AI Lead Management / White-label SaaS enhancement brief, Sections 1, 3–9, 15–18.
