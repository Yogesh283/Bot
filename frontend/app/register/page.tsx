"use client";

import Link from "next/link";
import { FormEvent, useState } from "react";

import { api, ApiError } from "@/lib/api";

export default function RegisterPage() {
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    setMessage("");
    try {
      const response = await api<{ message: string }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          email: String(form.get("email") ?? ""),
          full_name: String(form.get("full_name") ?? ""),
          password: String(form.get("password") ?? ""),
        }),
      });
      setMessage(response.message);
      event.currentTarget.reset();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Registration failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-4 py-8">
      <p className="text-xs uppercase tracking-[0.18em] text-tide">Create account</p>
      <h1 className="mt-2 text-3xl font-semibold">Register</h1>
      <p className="mt-2 text-sm leading-6 text-mist">
        New accounts are ordinary users. Administrator access is granted later by the local bootstrap command, and only
        after the email is verified.
      </p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block text-sm">
          Name
          <input name="full_name" required minLength={1} maxLength={120} className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-3" />
        </label>
        <label className="block text-sm">
          Email
          <input name="email" type="email" autoComplete="email" required className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-3" />
        </label>
        <label className="block text-sm">
          Password
          <input
            name="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={12}
            maxLength={128}
            className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-3"
          />
          <span className="mt-1 block text-xs text-mist">12 to 128 characters, with a letter and a number.</span>
        </label>
        {error ? <p className="text-sm text-signal">{error}</p> : null}
        {message ? <p className="text-sm leading-6 text-tide">{message}</p> : null}
        <button type="submit" disabled={pending} className="min-h-12 w-full rounded-xl bg-tide font-semibold text-ink disabled:opacity-60">
          {pending ? "Creating account…" : "Create account"}
        </button>
      </form>
      <Link href="/login" className="mt-6 text-sm text-mist">
        Already registered? Sign in
      </Link>
    </main>
  );
}
