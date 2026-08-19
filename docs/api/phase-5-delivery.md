# Phase 5 Delivery API

Phase 5 introduces tenant-scoped Projects, Design Control, Estimation and BOQ APIs beneath `/api/v1`.
Every endpoint requires a valid user session, active company membership, `X-Company-Id`, and the named semantic permission.

## Projects

- `GET /projects/summary`
- `GET|POST /projects/stages`
- `GET|POST /projects/items`
- `GET /projects/{project_id}`
- `POST /projects/{project_id}/transition`
- `POST /projects/{project_id}/baseline`
- `GET /projects/{project_id}/baselines`
- `GET|POST /projects/{project_id}/wbs`
- `GET|POST /projects/{project_id}/tasks`
- `POST /projects/tasks/{task_id}/transition`

Projects and tasks use company-configurable `DeliveryStage` records. Transitions require an expected aggregate version. Project baselines are immutable snapshots of the project, WBS and tasks.

## Design control

- `GET /design/summary`
- `GET|POST /design/documents`
- `GET|POST /design/documents/{document_id}/versions`
- `GET /design/versions/{version_id}`
- `POST /design/versions/{version_id}/transition`
- `GET|POST /design/versions/{version_id}/reviews`
- `POST /design/reviews/{review_id}/decision`
- `GET|POST /design/issues`
- `POST /design/issues/{issue_id}/close`
- `GET|POST /design/transmittals`

Issued revisions can be included in transmittals. A newly issued revision supersedes the previous current issued revision for that document.

## Estimation and BOQ

- `GET /estimation/summary`
- `GET|POST /estimation/estimates`
- `GET /estimation/estimates/{estimate_id}`
- `GET|POST /estimation/estimates/{estimate_id}/versions`
- `POST /estimation/versions/{version_id}/transition`
- `POST /estimation/versions/{version_id}/baseline`
- `GET|POST /estimation/versions/{version_id}/sections`
- `GET|POST /estimation/versions/{version_id}/items`
- `GET /estimation/estimates/{estimate_id}/baselines`

Money uses fixed-precision decimals. BOQ totals are recalculated transactionally. Baselined versions are immutable and retain sections and item snapshots.
