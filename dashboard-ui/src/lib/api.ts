import "server-only";

const BASE = process.env.DASHBOARD_API_BASE_URL ?? "http://localhost:8000";
const USER = process.env.DASHBOARD_USER ?? "admin";
const PWD = process.env.DASHBOARD_PASSWORD ?? "change-me-please";

function authHeader(): string {
  return "Basic " + Buffer.from(`${USER}:${PWD}`).toString("base64");
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: authHeader(),
      ...(init.headers ?? {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`${path} failed: ${res.status} ${await res.text()}`);
  }
  return res.json() as Promise<T>;
}
