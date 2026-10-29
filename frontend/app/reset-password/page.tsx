"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { FormEvent, Suspense, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

function ResetForm() {
  const params = useSearchParams();
  const [token, setToken] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    const value = params.get("token") ?? "";
    setToken(value);
    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState({}, "", url.pathname);
  }, [params]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const response = await api<{ message: string }>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ token, password: String(form.get("password") ?? "") }),
      });
      setMessage(response.message);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Reset failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-4">
      <h1 className="text-3xl font-semibold">Choose a new password</h1>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block text-sm">
          New password
          <input
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={128}
            className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-3"
          />
        </label>
        {error ? <p className="text-sm text-signal">{error}</p> : null}
        {message ? <p className="text-sm text-tide">{message}</p> : null}
        <button type="submit" disabled={pending || !token} className="min-h-12 w-full rounded-xl bg-tide font-semibold text-ink disabled:opacity-60">
          {pending ? "Updating…" : "Update password"}
        </button>
      </form>
      <Link href="/login" className="mt-6 text-sm text-mist">
        Back to sign in
      </Link>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<main className="px-4 py-10 text-sm text-mist">Loading…</main>}>
      <ResetForm />
    </Suspense>
  );
}
