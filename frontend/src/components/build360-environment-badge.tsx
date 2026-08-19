export type Build360Environment = "development" | "testing" | "demo" | "production";

const LABELS: Record<Build360Environment, string> = {
  development: "DEVELOPMENT",
  testing: "TESTING",
  demo: "DEMO",
  production: "PRODUCTION",
};

const CLASSES: Record<Build360Environment, string> = {
  development: "border-sky-200 bg-sky-50 text-sky-900",
  testing: "border-violet-200 bg-violet-50 text-violet-900",
  demo: "border-amber-300 bg-amber-50 text-amber-950",
  production: "border-emerald-200 bg-emerald-50 text-emerald-950",
};

export function normalizeBuild360Environment(value?: string): Build360Environment {
  const normalized = (value || "development").trim().toLowerCase();
  if (normalized === "test" || normalized === "testing") return "testing";
  if (normalized === "demo") return "demo";
  if (normalized === "production" || normalized === "prod") return "production";
  return "development";
}

export function Build360EnvironmentBadge({
  environment,
  version,
}: Readonly<{ environment: Build360Environment; version: string }>) {
  return (
    <div
      aria-label={`Build360 ${LABELS[environment]} environment, version ${version}`}
      className={`fixed bottom-[5.4rem] right-3 z-[35] rounded-full border px-3 py-1.5 text-[10px] font-black tracking-[0.14em] shadow-sm backdrop-blur lg:bottom-4 lg:right-4 ${CLASSES[environment]}`}
      data-build360-environment={environment}
      data-build360-version={version}
      role="status"
    >
      {LABELS[environment]} · v{version}
    </div>
  );
}
