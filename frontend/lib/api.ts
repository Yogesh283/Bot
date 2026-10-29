import type { TokenResponse } from "@/lib/types";

const base = process.env.NEXT_PUBLIC_API_BASE ?? "/backend";

let accessToken: string | null = null;

export class ApiError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function setAccessToken(token: string | null) {
  accessToken = token;
}

export function getAccessToken() {
  return accessToken;
}

async function readDetail(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") {
      return body.detail;
    }
    if (Array.isArray(body.detail) && body.detail[0] && typeof body.detail[0] === "object") {
      const message = (body.detail[0] as { msg?: unknown }).msg;
      if (typeof message === "string") {
        return message;
      }
    }
  } catch {
    return "The server could not complete that request.";
  }
  return "The server could not complete that request.";
}

export async function refreshSession(): Promise<boolean> {
  const response = await fetch(`${base}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    setAccessToken(null);
    return false;
  }
  const body = (await response.json()) as TokenResponse;
  setAccessToken(body.access_token);
  return true;
}

export async function api<T>(path: string, options: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }
  const response = await fetch(`${base}${path}`, {
    ...options,
    headers,
    credentials: "include",
  });
  if (response.status === 401 && retry && !path.startsWith("/auth/")) {
    const refreshed = await refreshSession();
    if (refreshed) {
      return api<T>(path, options, false);
    }
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readDetail(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}
