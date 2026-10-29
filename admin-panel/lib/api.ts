const base = `${process.env.NEXT_PUBLIC_ADMIN_PATH || ""}/backend`;
const storageKey = "control_access_token";

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken() {
  return window.sessionStorage.getItem(storageKey);
}

export function setToken(token: string | null) {
  if (token) {
    window.sessionStorage.setItem(storageKey, token);
  } else {
    window.sessionStorage.removeItem(storageKey);
  }
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  const token = getToken();
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${base}${path}`, { ...init, headers });
  if (!response.ok) {
    let message = "The request failed.";
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") {
        message = body.detail;
      }
    } catch {
      message = "The request failed.";
    }
    throw new ApiError(response.status, message);
  }
  return (await response.json()) as T;
}
