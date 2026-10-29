"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { ApiError, api } from "@/lib/api";
import type { DashboardStatus } from "@/lib/types";

export default function SubscriptionPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [status, setStatus] = useState<DashboardStatus | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    if (ready && !user) {
      router.replace("/login");
    }
  }, [ready, user, router]);

  useEffect(() => {
    if (!user) {
      return;
    }
    api<DashboardStatus>("/dashboard/status")
      .then(setStatus)
      .catch((caught: unknown) => {
        setError(caught instanceof ApiError ? caught.message : "The plan could not be loaded.");
      });
  }, [user]);

  if (!ready || !user) {
    return <main className="px-4 py-10 text-sm text-mist">Loading your session…</main>;
  }

  const plan = status?.subscription;

  return (
    <AppShell>
      <h1 className="text-3xl font-semibold">Plan</h1>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-mist">
        This local Demo plan is stored by a fake payment provider. No card is charged. An inactive plan blocks Start
        Bot. Live trading stays off, and a plan does not promise profit. Demo trading can lose the whole practice balance.
      </p>
      {error ? <p className="mt-4 text-sm text-signal">{error}</p> : null}
      <section className="mt-5 rounded-2xl border border-line bg-panel p-4">
        <p className="text-xs uppercase tracking-wide text-mist">Status</p>
        <p className="mt-2 text-2xl font-semibold">{plan?.status ?? "Loading"}</p>
        <p className="mt-2 text-sm text-mist">Name: {plan?.plan ?? "…"}</p>
        <p className="mt-1 text-sm text-mist">
          Expiry: {plan?.expires_at ? new Date(plan.expires_at).toLocaleString() : "Not set"}
        </p>
      </section>
    </AppShell>
  );
}
