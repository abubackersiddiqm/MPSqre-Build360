export type DomainResolutionEnvironment = {
  build360PublicWebUrl?: string;
  vercelUrl?: string;
  vercelProjectProductionUrl?: string;
};

function hostnameFromUrlLike(value: string | undefined): string {
  const candidate = value?.trim();
  if (!candidate) return "";
  try {
    const parsed = new URL(candidate.includes("://") ? candidate : `https://${candidate}`);
    return parsed.hostname.trim().toLowerCase().replace(/\.$/, "");
  } catch {
    return "";
  }
}

export function normalizeRequestHost(rawHost: string): string {
  const first = rawHost.split(",", 1)[0]?.trim() ?? "";
  if (!first) return "";

  if (first.startsWith("[")) {
    const closing = first.indexOf("]");
    if (closing > 1) {
      return first.slice(1, closing).trim().toLowerCase().replace(/\.$/, "");
    }
  }

  return (first.split(":", 1)[0] ?? "").trim().toLowerCase().replace(/\.$/, "");
}

export function shouldResolveTenantDomainBrand(
  host: string,
  environment: DomainResolutionEnvironment,
): boolean {
  const normalizedHost = normalizeRequestHost(host);
  if (!normalizedHost) return false;

  if (
    normalizedHost === "localhost" ||
    normalizedHost === "127.0.0.1" ||
    normalizedHost === "::1"
  ) {
    return false;
  }

  const platformHosts = new Set(
    [
      hostnameFromUrlLike(environment.build360PublicWebUrl),
      hostnameFromUrlLike(environment.vercelUrl),
      hostnameFromUrlLike(environment.vercelProjectProductionUrl),
    ].filter(Boolean),
  );

  return !platformHosts.has(normalizedHost);
}
