import "server-only";

import { accessToken, backendUrl } from "./server-session";

export type PlatformBackendResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number };

export async function platformBackendRequest<T>(
  path: string,
): Promise<PlatformBackendResult<T>> {
  const token = await accessToken();
  if (!token) {
    return { ok: false, status: 401 };
  }
  const response = await fetch(backendUrl(path), {
    headers: {
      Authorization: `Bearer ${token}`,
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
