# Phase 20 People Operations API

Base path: `/api/v1/people/`

All endpoints require a valid access token, an active company membership, an `X-Company-Id` header, and the semantic permission documented below.

## Dashboard and portfolio

- `GET summary` — `people.dashboard.read`
- `GET portfolio` — `people.dashboard.read`

The portfolio returns tenant-scoped employees, departments, employment contracts, leave policies and balances, leave requests, timesheets, and payroll evidence. Protected operations remain permission-controlled on their dedicated mutation endpoints.

## Leave

- `GET leave-requests` — `people.leave.read`
- `POST leave-requests` — `people.leave.request`
- `POST leave-requests/{public_id}/transition` — `people.leave.approve`

Leave requests are self-service. Approval and rejection enforce independent reviewer controls, optimistic concurrency, overlap validation, and non-negative leave balances.

## Timesheets

- `GET timesheets` — `people.timesheet.read`
- `POST timesheets` — `people.timesheet.create`
- `POST timesheets/{public_id}/transition` — `people.timesheet.approve`

Timesheets are self-service, start on Monday, limit each line to 24 hours, limit each week to 168 hours, validate project tenancy, and prevent duplicate employee/week submissions.

## Payroll evidence

- `GET payroll-runs` — `people.payroll.read`
- `POST payroll-runs` — `people.payroll.manage`
- `POST payroll-runs/{public_id}/transition` — permission selected from the target state:
  - lock or cancel — `people.payroll.manage`
  - approve — `people.payroll.approve`
  - post — `people.payroll.post`

Payroll runs require maker-checker approval before posting. Posted runs store SHA-256 evidence. Phase 20 does not calculate jurisdiction-specific taxes, provident fund, social insurance, or other statutory deductions until the corresponding localization policy is configured and independently validated.
