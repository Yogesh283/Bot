"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { api, ApiError } from "@/lib/api";

export default function ForgotPasswordPage() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const response = await api<{ message: string }>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ email: String(form.get("email") ?? "") }),
      });
      setMessage(response.message);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Request failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-4">
      <h1 className="text-3xl font-semibold">Reset password</h1>
      <p className="mt-2 text-sm leading-6 text-mist">
        If the email belongs to a verified account, the API console prints a reset link. The response is the same when
        the email is unknown.
      </p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block text-sm">
          Email
          <input name="email" type="email" required autoComplete="email" className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-3" />
        </label>
        {error ? <p className="text-sm text-signal">{error}</p> : null}
        {message ? <p className="text-sm text-tide">{message}</p> : null}
        <button type="submit" disabled={pending} className="min-h-12 w-full rounded-xl bg-tide font-semibold text-ink disabled:opacity-60">
          {pending ? "Sending…" : "Send reset link"}
        </button>
      </form>
      <Link href="/login" className="mt-6 text-sm text-mist">
        Back to sign in
      </Link>
    </main>
  );
}
