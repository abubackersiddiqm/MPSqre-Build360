# Build360 v1.0.0 environments

Build360 uses four deliberately separate runtime environments and databases.

| Environment | Database | Intended use |
|---|---|---|
| DEVELOPMENT | `build360_development` | Daily local coding and manual development |
| TESTING | `build360_testing` | Automated tests and destructive QA data |
| DEMO | `build360_demo` | Customer/investor demonstrations with synthetic data |
| PRODUCTION | `build360_production` (or the real hosted production DB name) | Live customer data only |

Set `BUILD360_ENVIRONMENT` to select the environment. `DJANGO_ENV_FILE` may explicitly select a file. The backend validates `BUILD360_DATABASE_NAME_GUARD` against the database name, and demo seeding refuses to run anywhere except DEMO.

The UI always displays `<ENVIRONMENT> · v1.0.0`. Never hide the label in demo/testing/development. Production shows a smaller production badge as deployment evidence.

Real `backend/.env.*` files are secrets and are Git-ignored. Commit only `*.example` templates.
