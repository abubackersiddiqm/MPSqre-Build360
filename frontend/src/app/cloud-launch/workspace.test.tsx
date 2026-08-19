import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CloudLaunchWorkspace, type CloudopsPortfolio } from "./workspace";

const data: CloudopsPortfolio = {
  current_user_public_id: "00000000-0000-0000-0000-000000000001",
  summary: {
    targets: 3,
    active_targets: 1,
    production_targets: 1,
    pipelines: 3,
    deployments: 0,
    failed_deployments: 0,
    latest_deployment_status: null,
    backup_policies: 4,
    verified_backups: 1,
    latest_backup_status: "verified",
    passed_restore_exercises: 1,
    secrets_due: 0,
  },
  environments: [],
  targets: [
    {
      public_id: "00000000-0000-0000-0000-000000000002",
      environment: {
        public_id: "00000000-0000-0000-0000-000000000003",
        code: "LOCAL",
        name: "Local Windows",
        environment_type: "local",
        base_url: "http://localhost:3000",
        region: "local",
        data_residency: "local",
        is_active: true,
      },
      code: "LOCAL_NATIVE",
      name: "Native Windows validation",
      provider: "generic",
      region: "local",
      data_residency: "local",
      backend_service: "Django",
      frontend_service: "Next.js",
      database_service: "PostgreSQL",
      cache_service: "Local memory",
      object_storage_service: "S3-compatible",
      worker_service: "Celery eager",
      secret_manager_service: "backend/.env",
      status: "active",
      production_approved: false,
      version: 1,
    },
  ],
  pipelines: [],
  deployments: [],
  backup_policies: [],
  backup_executions: [],
  restore_exercises: [],
  secret_policies: [],
};

describe("CloudLaunchWorkspace", () => {
  it("shows governed cloud launch posture", () => {
    render(<CloudLaunchWorkspace initialData={data} />);
    expect(screen.getByText("Production deployment and recovery")).toBeTruthy();
    expect(screen.getByText("Phase 18 active")).toBeTruthy();
    expect(screen.getByText("Native Windows validation")).toBeTruthy();
    expect(screen.getByText("Verified backups")).toBeTruthy();
  });
});
