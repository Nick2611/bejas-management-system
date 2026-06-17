interface ApiError {
  detail?:
    | string
    | Array<{ msg?: string }>
    | { message?: string; code?: string };
  message?: string;
}

export const API_URL = (
  import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
).replace(/\/$/, '');

export const UNAUTHORIZED_EVENT = 'bejas:unauthorized';

export function getApiErrorMessage(
  payload: unknown,
  status: number,
  fallback: string
): string {
  const error = payload as ApiError | null;
  const detail = Array.isArray(error?.detail)
    ? error.detail.map(item => item.msg).filter(Boolean).join('. ')
    : typeof error?.detail === 'object'
      ? error.detail.message
      : error?.detail;

  return detail || error?.message || `${fallback} (HTTP ${status})`;
}

interface RequestOptions {
  auth?: boolean;
  token?: string;
  fallback?: string;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  options: RequestOptions = {}
): Promise<T> {
  const token = options.token
    ?? (options.auth === false ? null : localStorage.getItem('bejas_access_token'));
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...(init.body ? { 'Content-Type': 'application/json' } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers
    }
  });

  const payload = response.status === 204
    ? null
    : await response.json().catch(() => null) as unknown;

  if (!response.ok) {
    if (response.status === 401 && options.auth !== false) {
      window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    }
    throw new Error(
      getApiErrorMessage(
        payload,
        response.status,
        options.fallback ?? 'La operación no pudo completarse'
      )
    );
  }

  return payload as T;
}
