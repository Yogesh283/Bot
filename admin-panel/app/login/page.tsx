"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const body = await api<{ access_token: string }>("/control/login", {
        method: "POST",
        body: JSON.stringify({
          username: String(form.get("username") ?? ""),
          password: String(form.get("password") ?? ""),
        }),
      });
      setToken(body.access_token);
      router.replace("/");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Sign-in failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md items-center px-6">
      <form onSubmit={onSubmit} className="w-full rounded-lg border border-[#d7dee7] bg-white p-8 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-[#5c6b7a]">Admin desk</p>
        <h1 className="mt-2 text-2xl font-semibold">Sign in</h1>
        <p className="mt-2 text-sm text-[#5c6b7a]">This login is only for the admin desk. It is not a trading account.</p>
        <label className="mt-6 block text-sm font-medium">
          Username
          <input name="username" autoComplete="username" required className="mt-1 h-11 w-full rounded border border-[#c5ced8] px-3" />
        </label>
        <label className="mt-4 block text-sm font-medium">
          Password
          <input name="password" type="password" autoComplete="current-password" required className="mt-1 h-11 w-full rounded border border-[#c5ced8] px-3" />
        </label>
        {error ? <p className="mt-3 text-sm text-[#b42318]">{error}</p> : null}
        <button type="submit" disabled={pending} className="mt-6 h-11 w-full rounded bg-[#16324f] font-semibold text-white disabled:opacity-60">
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </main>
  );
}
