export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

export async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function apiMutate<T>(
  path: string,
  options: { method: string; body?: unknown },
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: options.method,
    headers: { "Content-Type": "application/json" },
    ...(options.body ? { body: JSON.stringify(options.body) } : {}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
    throw new Error(err.detail || `API error: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
