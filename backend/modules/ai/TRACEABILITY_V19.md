# v0.45.2.19 — CRM AI Lead Intelligence

- **AI-CRM-001** — Reuse existing AIProviderProfile / AIModelPolicy / AIInteraction / AICitation governance.
- **AI-CRM-002** — AIEntityInsight is a generic latest-result cache, not a second CRM Lead table.
- **AI-CRM-003** — Lead source digest is computed from meaningful Lead, Activity and StageHistory fields.
- **AI-CRM-004** — Repeated refresh with unchanged source digest reuses the cached interaction.
- **AI-CRM-005** — New/changed lead log-book evidence makes the cached result stale without page-load regeneration.
- **AI-CRM-006** — Summary and recommendation entitlements are independently enforced at backend service boundaries.
- **AI-CRM-007** — Recommendations are advisory only and never change stage, create activity, send communication or reveal protected contact endpoints.
- **AI-CRM-008** — Every generated output creates/uses AI citations pointing to the authorized CRM source records.
- **AI-CRM-009** — Human override is explicit, audited, visually identified and preserved across later AI regeneration until cleared.
- **AI-CRM-010** — Local grounded provider is the only execution adapter enabled for this version; no external LLM credentials or network calls are introduced.
- **AI-CRM-011** — Meta Ads source is used as context only after v18 has already converted the external lead into governed CRM records.
- **AI-CRM-012** — Protected phone/email values are not intentionally retrieved into the CRM AI context builder.
