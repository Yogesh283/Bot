"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";

import { useAuth } from "@/components/auth-provider";
import { ApiError } from "@/lib/api";

export default function LoginPage() {
  const { signIn } = useAuth();
  const router = useRouter();
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      await signIn(String(form.get("email") ?? ""), String(form.get("password") ?? ""));
      router.replace("/dashboard");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Sign-in failed.");
    } finally {
      setPending(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-4 py-8">
      <p className="text-xs uppercase tracking-[0.18em] text-tide">Sign in</p>
      <h1 className="mt-2 text-3xl font-semibold">Welcome back</h1>
      <p className="mt-2 text-sm leading-6 text-mist">Use the email address you verified.</p>
      <form onSubmit={onSubmit} className="mt-6 space-y-4">
        <label className="block text-sm">
          Email
          <input
            name="email"
            type="email"
            autoComplete="email"
            required
            className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-3"
          />
        </label>
        <label className="block text-sm">
          Password
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            required
            className="mt-1 w-full rounded-xl border border-line bg-panel px-3 py-3"
          />
        </label>
        {error ? <p className="text-sm text-signal">{error}</p> : null}
        <button type="submit" disabled={pending} className="min-h-12 w-full rounded-xl bg-tide font-semibold text-ink disabled:opacity-60">
          {pending ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <div className="mt-6 flex justify-between text-sm text-mist">
        <Link href="/register">Create account</Link>
        <Link href="/forgot-password">Forgot password</Link>
      </div>
    </main>
  );
}
