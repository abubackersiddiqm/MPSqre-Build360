# Phase 16 Pilot Operations API

Base path: `/api/v1/pilotops/`

The API is tenant-scoped and requires a valid access token, `X-Company-Id`, active membership and semantic permissions.

## Read APIs

- `GET summary` — headline readiness and adoption metrics.
- `GET portfolio` — current program, checklist, master data, training, latest assessment, go-live plan and adoption evidence.

## Controlled actions

- `POST checklist/{public_id}/transition`
- `POST programs/{program_public_id}/validate-master-data`
- `POST training/{public_id}/complete`
- `POST programs/{program_public_id}/assess-readiness`
- `POST signoffs/{public_id}/decide`
- `POST go-live/{public_id}/transition`
- `POST programs/{program_public_id}/collect-adoption`

Material actions require optimistic versions where applicable and append audit evidence. Readiness and adoption evidence is checksum-backed. Go-live approval is maker-checker controlled, and no automated cutover execution is performed by the API.
