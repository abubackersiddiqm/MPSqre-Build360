# v0.45.2.18 — Meta Lead Ads Ingestion

- **META-001** — Reuse ConnectorProfile and DataMappingProfile; no parallel integration registry.
- **META-002** — Meta credentials remain behind ConnectorProfile.secret_ref; adapter supports env:// references and never serializes raw token/app secret.
- **META-003** — Public webhook verifies the configured one-time verification token and HMAC request signature before accepting payload.
- **META-004** — Webhook receipt is idempotent by connector + external lead ID.
- **META-005** — Only configured Page ID / form IDs can create receipts.
- **META-006** — Background processing retrieves lead field_data, applies published DataMappingProfile, and writes existing CRM Contact + Lead.
- **META-007** — Existing contact duplicate detection is reused; active lead for the contact is reused rather than duplicated.
- **META-008** — Lead source is META_ADS; Meta IDs are preserved as integration evidence / CRM activity metadata.
- **META-009** — Tenant permission and subscription entitlement are enforced at backend API/service boundaries.
- **META-010** — Raw webhook field values are not persisted in MetaLeadReceipt; CRM protected phone/email continue to use CRM encryption/blind indexes.
- **META-011** — Retry is explicit and tenant scoped.
- **META-012** — AI summary/recommendation remains out of scope for v18 and follows after Meta ingestion stabilizes.
