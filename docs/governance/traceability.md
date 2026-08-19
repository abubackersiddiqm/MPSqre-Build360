# Requirement traceability

Product Bible baseline: v0.1, 29 July 2026.

| Requirement | Foundation evidence | Verification |
|---|---|---|
| GOV-002 | Public identifier primitive in `platform.models` | backend unit tests |
| GOV-010 | Celery configuration, correlation metadata, health checks | worker and health tests |
| ADR-001 | Bounded-context package template and import contract | architecture test |
| ADR-002 | PostgreSQL and MinIO services; no binary DB model | Compose validation |
| ADR-003 | Outbox event primitive and publishing boundary | backend unit tests |
| ADR-008 | Redis/Celery worker and scheduler services | Compose validation |
| ADR-009 | S3-compatible environment contract and MinIO service | Compose validation |
| GOV-001 | Authenticated membership-derived tenant context and tenant API base | API and isolation tests |
| GOV-004 | Append-only audit event service with request/device context | audit tests |
| IAM-001 | Non-destructive user lifecycle and invitation records | domain/API tests |
| IAM-002 | Short access JWT, rotating single-use refresh JWT, session revocation | token security tests |
| IAM-003 | Effective membership roles and semantic permission checks | permission tests |
| IAM-005 | Recent-assurance policy primitive for privileged commands | policy tests |
| CMP-001 | Company localization and legal identity foundation | model/service tests |
| CMP-002 | Effective-dated company locations | model tests |
| EMP-001 | Tenant-owned employee profile linked to membership | isolation tests |
| EMP-002 | Effective-dated manager relationship history | domain tests |

| GOV-003 | Immutable configuration and workflow versions with effective dates | configuration/workflow tests |
| GOV-005 | Private object storage metadata, presigned access, checksum and scan state | file governance tests |
| CFG-001 | Global definitions and tenant-owned configuration versions | configuration tests |
| CFG-002 | Published versions are immutable and effective-dated | model/service tests |
| CFG-003 | Workflow states and transitions are validated configuration | workflow tests |
| SUB-001 | Versioned plans and tenant subscriptions | entitlement tests |
| SUB-002 | Server-side effective entitlements and limits | entitlement API/service tests |
| SUB-003 | Effective-dated overrides without plan mutation | override tests |
| AUD-001 | Tenant-scoped append-only audit search | audit API tests |
| AUD-002 | Actor, request, correlation, entity and before/after evidence | audit tests |
| AUD-003 | Material configuration/workflow/file actions append audit facts | service tests |
| AUD-004 | Audit update/delete blocked by database and model controls | append-only tests |
| BR-GOV-002 | Status and approval behavior represented by versions, not hardcoded roles | workflow tests |
| BR-GOV-004 | Material commands write audit evidence and outbox facts atomically | transaction tests |
| BR-GOV-005 | Effective dates and version retention for in-flight behavior | configuration/workflow tests |
| BR-GOV-006 | Semantic permissions gate management, publishing and approvals | API permission tests |
| BR-GOV-007 | File bytes remain private object storage with governed metadata | file tests |
| BR-GOV-008 | Outbox claim, retry, publish and dead-letter lifecycle | outbox tests |

Phase 3 supplies configuration publishing, workflow/approval controls,
entitlements, governed private-file metadata and access, audit search, and
outbox delivery controls. Provider adapters, malware scan workers, PostgreSQL
RLS, offline behavior, business modules, and production operating runbooks
remain outside this release slice.


## Phase 8 finance and commercial controls

| Requirement | Phase 8 evidence | Verification |
|---|---|---|
| FIN-001 | Tenant-owned project budgets and cost-code lines | model/service tests |
| FIN-002 | Commitment, actual, accrual, forecast and variation ledger types | ledger tests |
| FIN-003 | Client/vendor invoices, tax hooks, due dates and ageing | API/service tests |
| FIN-004 | Payment and retention-release lifecycle | payment tests |
| FIN-005 | Effective financial periods and irreversible period locks | period-lock tests |
| FIN-006 | Append-only commercial ledger and accounting-grade source idempotency | append-only/idempotency tests |
| API-FIN-001 | Tenant-scoped `/api/v1/finance` summary and register APIs | API smoke test |
| UJ-FIN-001 | Budget → variation → invoice → payment commercial flow | Phase 8 smoke test |

Phase 8 intentionally provides configuration hooks rather than jurisdiction-specific tax advice. Regional statutory validation and accounting integration remain product-owner decisions.

## Phase 9 communications and notifications

| Requirement | Phase 9 evidence | Verification |
|---|---|---|
| COM-001 | Provider-neutral communication request and adapter contract | adapter/service tests |
| COM-002 | Tenant channel policies, consent evidence, quiet hours and subject limits | policy/consent tests |
| COM-003 | Versioned locale/channel templates with controlled publishing | template tests |
| COM-004 | Signed callbacks, replay-safe event IDs and payload digests | callback tests |
| COM-005 | Inbound correlation queue without ordinary raw endpoint exposure | callback/inbound tests |
| COM-006 | CRM and other modules interact through communication requests, not providers | architecture/API boundary |
| NOT-001 | Tenant/user-scoped notification inbox and read lifecycle | notification tests |
| NOT-002 | Per-event/channel notification preferences and digest modes | preference tests |
| NOT-003 | Configurable routing rules and delivery evidence | rule/delivery tests |
| API-COM-001 | Tenant-scoped `/api/v1/communications` and `/api/v1/notifications` APIs | Phase 9 smoke test |
| BR-COM-001..006 | Consent, policy, provider isolation, callback verification and audit/outbox evidence | service/security tests |

Production communication providers, jurisdiction-specific consent packs,
recording retention, and telecom regulatory approval remain deployment-specific
configuration and validation responsibilities.

## Phase 10 reports, portals and operational maturity

| Requirement | Phase 10 evidence | Verification |
|---|---|---|
| RPT-001..004 | Metric catalogue, saved reports, immutable report snapshots, classified expiring CSV/XLSX/PDF exports | Reporting service tests and Phase 10 smoke test |
| POR-001..004 | Email-bound invitations, bounded grants, scoped shares, external portal workspace | Portal service tests and invitation acceptance flow |
| GOV-008..009 | Validation-first import staging, privacy request register, effective retention policies | Data operations tests and migration drift gate |
| GOV-010 | Audit/outbox evidence, report integrity, recovery verification register | Backend quality gate and recovery smoke checks |
| BR-GOV-007 | Export integrity and time-bound download controls | SHA-256 artifact test |

## Phase 11 governed AI foundations

| Requirement | Phase 11 evidence | Verification |
|---|---|---|
| AI-001 | Tenant-owned provider profiles and effective-dated model policies | Model, migration and bootstrap checks |
| AI-002 | Membership-authorized retrieval over governed metric sources | Permission and tenant-isolation tests |
| AI-003 | Response citations with source identity, version and classification | Grounded interaction tests |
| AI-004 | Digest-only extraction input, confidence evidence and human correction | Extraction privacy/review tests |
| AI-005 | Advisory risk signals and confirmation-gated tool proposals | Risk and independent-confirmation tests |
| AI-006 | Evaluation evidence, bounded outputs, retention and no autonomous execution | Guardrail evaluation suite |

External model providers are intentionally inactive. Phase 11 supplies the
provider abstraction and governance controls, not approval to process tenant
data with a third party.

## Phase 12 enterprise administration and reliability

| Control objective | Phase 12 evidence | Verification |
|---|---|---|
| Release governance | Environment-bound release records, SHA-256 evidence, readiness checks and maker-checker approval | Release service tests and smoke test |
| Operational reliability | Service objectives and append-oriented health snapshots | SLO/health API checks |
| Incident response | Severity, lifecycle, corrective action and mandatory postmortem controls | Incident transition tests |
| Change control | Approval-controlled feature flags and maintenance windows | Independent-approval tests |
| Recovery readiness | Seeded rollback, database outage and restore-verification runbooks | Bootstrap and dashboard checks |
| GOV-010 | Audit and transactional outbox evidence for material operational actions | Backend quality gate |

Phase 12 supplies governance and operational evidence. It does not claim that a
local development workstation meets production availability, backup, security,
or regulatory requirements.


## Phase 13 — SaaS control plane and tenant lifecycle

| Requirement area | Implementation evidence |
|---|---|
| Configurable platform operators | `controlplane.PlatformRole`, role permissions, effective assignments |
| Tenant lifecycle | `controlplane.TenantAccount`, optimistic lifecycle transitions, company suspension/activation |
| Plans and subscriptions | Published immutable `subscription.PlanVersion` plus governed assignment service |
| Usage and quotas | Append-only `controlplane.TenantUsageSnapshot` with checksummed metrics and quota status |
| Support access governance | Time-bound request and tenant decision records; no impersonation token execution |
| Audit and events | Control-plane lifecycle, subscription, usage, and support facts append audit/outbox evidence |

## Phase 14 — Globalization and Integration Hub

| Requirement area | Evidence |
|---|---|
| GOV-006 localization | `integration.LocalizationPack`, versioned publication and regional seed catalogue |
| BR-GOV-009 regional configuration | Country, locale, currency, timezone, units, tax and address schemas |
| API integration governance | Connector profiles, API client digests, semantic scopes and secret references |
| Event integration | Tenant-scoped webhook subscriptions and delivery evidence |
| Data exchange | Published mapping profiles and idempotent synchronization runs |
| Audit/outbox | Material Phase 14 service actions append audit and business-event evidence |
| UI | `/integrations` permission-aware workspace |
| Tests | Localization checksum, append-only FX, secret rotation and sync idempotency tests |

## Phase 15 — Unified Mobile PWA and Workspace Experience

| Control | Evidence |
|---|---|
| Capability-driven navigation | `frontend/src/lib/navigation/workspaces.ts` filters every workspace by effective permissions and platform-operator context |
| Unified responsive shell | `frontend/src/components/app-shell.tsx` provides desktop sidebar, mobile navigation, tenant context, notification badge and account controls |
| Command palette | Authorized workspace search is available through Ctrl/Cmd+K and mobile search controls |
| PWA boundary | `frontend/src/app/manifest.ts`, generated icons and `frontend/public/sw.js` provide installability without caching authenticated business pages |
| Offline safety | `/offline` documents that protected tenant data is network-only while approved field sync remains separately governed |
| Accessibility | Skip link, semantic navigation, focus-visible controls, reduced-motion support and labelled dialogs are part of the shared shell |
| Validation | Workspace authorization tests, TypeScript syntax validation, PWA asset checks and frontend quality gates |


## v0.15.2 — Backend consistency and installer compatibility hotfix

| Control | Evidence |
|---|---|
| Migration reproducibility | `vendor.0002_remove_supplystage_supply_stage_range_valid_and_more` records the normalized `SupplyStage` effective-date check constraint state |
| Generated-migration compatibility | The installer validates the expected operation set semantically, permits formatting and quote-style differences, rejects unexpected operations, and normalizes accepted source to the controlled copy |
| Decimal precision | Finance, procurement and integration serializer minimums use exact `Decimal` instances |
| Regression prevention | `test_decimal_serializer_contracts.py` verifies all affected minimum-value contracts |
| Migration impact | No new schema change; `vendor.0002` remains the only vendor constraint-normalization migration |
| Acceptance evidence | Warning-free Django checks, zero migration drift, applied `vendor.0002`, exact Decimal serializer tests, and versioned checksum verification |

## Phase 16 — Pilot Operations and Go-Live Readiness

| Control objective | Phase 16 evidence | Verification |
|---|---|---|
| Guided pilot onboarding | `pilotops.PilotProgram` and required checklist portfolio | Initializer and API smoke test |
| Master-data readiness | Live tenant record counters with minimum thresholds and evidence | Validation service tests |
| Training and adoption | Published training modules, membership assignments and append-only adoption snapshots | Training/adoption tests |
| Readiness governance | Checksummed append-only readiness assessments with blockers and warnings | Readiness service tests |
| Go-live governance | Versioned cutover plan, independent approval, required sign-offs and rollback transition | Maker-checker tests |
| Tenant isolation | Every Phase 16 aggregate leads with `company` and validates cross-company relationships | Cross-tenant API tests |
| Audit and events | Checklist, readiness, adoption and go-live actions append audit/outbox evidence | Backend quality gate |
| UX | Permission-aware `/pilot-readiness` workspace in the unified shell | Frontend and smoke tests |

## Phase 17 — Security and Compliance Operations

| Control objective | Phase 17 evidence | Verification |
|---|---|---|
| Security-control catalogue | Published company-scoped readiness frameworks and 24 seeded baseline controls | Initializer and portfolio API |
| Evidence-backed assessment | Versioned assessments, control evaluations, calculated score and SHA-256 evidence digest | Assessment service tests |
| Independent assurance | Assessor/reviewer separation for assessment approval | Maker-checker regression tests |
| Risk governance | Likelihood × impact scoring, treatment plans, acceptance and closure history | Risk validation tests |
| Security exceptions | Time-bound exceptions, compensating controls and independent approval | Exception transition tests |
| Access certification | Role-assignment campaigns, item-level retain/remove/modify decisions and independent approval | Access-review tests |
| Tenant isolation | Every Phase 17 aggregate leads with `company` and validates cross-company relationships | API and service tests |
| Audit and events | Material assessment, risk, exception and access-review actions append audit/outbox facts | Backend quality gate |
| UX | Permission-aware `/compliance` workspace in the unified shell | Frontend and smoke tests |

Phase 17 supplies operational readiness and assurance evidence. It does not claim ISO,
regulatory, privacy or customer certification.

## Phase 18 — Cloud Launch and Deployment Operations

| Control objective | Phase 18 evidence | Verification |
|---|---|---|
| Production topology | `cloudops.CloudTarget` binds governed runtime environments to documented managed services and residency | Target validation and bootstrap checks |
| Release promotion | `cloudops.DeploymentPipeline` and `DeploymentExecution` enforce quality gates, optimistic concurrency and maker-checker approval | Deployment governance tests |
| Backup governance | Versioned backup policies and checksummed backup execution evidence | Backup service tests and smoke test |
| Recovery readiness | Restore exercises capture measured RPO/RTO, evidence digest and independent approval | Restore maker-checker tests |
| Secret management | Secret-manager references only, rotation intervals and evidence; raw secret-like values are rejected | Secret validation and rotation tests |
| Production configuration | Django deployment checks reject wildcard hosts, plaintext object storage and PostgreSQL without TLS | `manage.py check --deploy` |
| CI/CD evidence | GitHub Actions quality and release-evidence workflows produce deterministic checksums | Workflow review and release gate |
| Operational tooling | Backup, restore, environment validation and smoke scripts under `infra/scripts` | Phase 18 acceptance scripts |
| Tenant isolation | Every cloudops aggregate leads with `company` and validates cross-company relationships | Backend service tests |
| Audit and events | Target, deployment, backup, restore and rotation actions append audit/outbox facts | Backend quality gate |
| UX | Permission-aware `/cloud-launch` workspace in the unified shell | Frontend and smoke tests |

Phase 18 supplies provider-neutral deployment governance and release evidence. It does not
activate or certify a specific cloud provider, managed backup product or external secret store.

## Phase 19 — Customer success and commercialization

Customer account health, subscription billing, support SLAs, adoption evidence and renewal governance are implemented by `modules.successops` and `/customer-success`.

## v0.19.1 maintenance evidence

- Customer-success adoption evidence uses a unique Company reverse accessor.
- `successops.0001_initial` and the live model state are synchronized before first application.
- Django system checks and regression tests guard the cross-module reverse-relation contract.

- Phase 20: people operations, leave, timesheets and payroll evidence (`modules.peopleops`).
