import "server-only";

import { accessToken, backendUrl, selectedCompany } from "./server-session";

export type BackendResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number };

export async function tenantBackendRequest<T>(path: string): Promise<BackendResult<T>> {
  const [token, companyPublicId] = await Promise.all([accessToken(), selectedCompany()]);
  if (!token || !companyPublicId) {
    return { ok: false, status: 401 };
  }

  const response = await fetch(backendUrl(path), {
    headers: {
      Authorization: `Bearer ${token}`,
      "X-Company-Id": companyPublicId,
      "X-Request-Id": crypto.randomUUID(),
    },
    cache: "no-store",
  }).catch(() => null);

  if (!response) {
    return { ok: false, status: 503 };
  }
  if (!response.ok) {
    return { ok: false, status: response.status };
  }
  return { ok: true, status: response.status, data: (await response.json()) as T };
}
