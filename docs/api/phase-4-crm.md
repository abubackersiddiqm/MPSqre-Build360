# Phase 4 CRM API

Base path: `/api/v1/crm`

All endpoints require:

- Bearer access token
- `X-Company-Id` for an active membership
- the relevant semantic permission

## Endpoints

| Method | Path | Permission | Purpose |
|---|---|---|---|
| GET | `/summary` | `crm.dashboard.read` | CRM KPI and pipeline summary |
| GET/POST | `/stages` | `crm.stage.read` / `crm.stage.manage` | Configurable lead and opportunity stages |
| GET/POST | `/customers` | `crm.customer.read` / `crm.customer.manage` | Customer catalogue |
| GET | `/customers/{id}` | `crm.customer.read` | Customer detail with masked contacts |
| GET/POST | `/contacts` | `crm.contact.read` / `crm.contact.manage` | Protected contacts |
| GET | `/contacts/duplicates` | `crm.contact.read` | Tenant-scoped blind-index duplicate check |
| POST | `/contacts/{id}/reveal` | `crm.contact.reveal` | Audited privileged reveal |
| GET/POST | `/leads` | `crm.lead.read` / `crm.lead.manage` | Lead pipeline |
| GET | `/leads/{id}` | `crm.lead.read` | Lead detail and timeline |
| POST | `/leads/{id}/transition` | `crm.lead.transition` | Optimistic stage transition |
| POST | `/leads/{id}/convert` | `crm.lead.convert` | Idempotent customer/opportunity conversion |
| GET/POST | `/opportunities` | `crm.opportunity.read` / `crm.opportunity.manage` | Opportunity pipeline |
| POST | `/opportunities/{id}/transition` | `crm.opportunity.transition` | Optimistic opportunity transition |
| GET/POST | `/activities` | `crm.activity.read` / `crm.activity.manage` | Calls, meetings, follow-ups, notes and site visits |

Protected email and phone values are encrypted at application level. Ordinary responses expose only masked values. Duplicate matching uses tenant-scoped blind indexes.
