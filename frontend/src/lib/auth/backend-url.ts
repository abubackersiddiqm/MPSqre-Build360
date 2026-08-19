const LOCAL_BACKEND_BASE_URL = "http://127.0.0.1:8000/api/v1";

function normalizeBaseUrl(value: string): string {
  return value.trim().replace(/\/+$/, "");
}

function isDockerOnlyHostname(value: string): boolean {
  try {
    return new URL(value).hostname === "api";
  } catch {
    return false;
  }
}

export function resolveBackendBaseUrl(
  configuredValue: string | undefined,
  nodeEnv: string | undefined,
): string {
  if (configuredValue?.trim()) {
    const configured = normalizeBaseUrl(configuredValue);
    if (nodeEnv !== "production" && isDockerOnlyHostname(configured)) {
      return LOCAL_BACKEND_BASE_URL;
    }
    return configured;
  }
  if (nodeEnv !== "production") {
    return LOCAL_BACKEND_BASE_URL;
  }
  throw new Error("INTERNAL_API_BASE_URL is not configured");
}

export function joinBackendUrl(baseUrl: string, path: string): string {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizeBaseUrl(baseUrl)}${normalizedPath}`;
}
