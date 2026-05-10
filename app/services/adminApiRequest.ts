export type AdminApiRequest = <T = unknown>(
  path: string,
  method?: string,
  body?: unknown,
) => Promise<T | undefined>;

export function buildApiPath(
  path: string,
  params?: Record<string, string | number | boolean | undefined | null>,
): string {
  if (!params) return path;

  const queryParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      queryParams.append(key, String(value));
    }
  }

  const query = queryParams.toString();
  return query ? `${path}?${query}` : path;
}

export function adminGet<T>(
  apiRequest: AdminApiRequest,
  path: string,
  params?: Record<string, string | number | boolean | undefined | null>,
): Promise<T | undefined> {
  return apiRequest<T>(buildApiPath(path, params));
}

export function adminMutation<T>(
  apiRequest: AdminApiRequest,
  method: 'POST' | 'PUT' | 'PATCH' | 'DELETE',
  path: string,
  body?: unknown,
): Promise<T | undefined> {
  return apiRequest<T>(path, method, body);
}
