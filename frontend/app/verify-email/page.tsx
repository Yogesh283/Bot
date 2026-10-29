"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";

const verificationRequests = new Map<string, Promise<string>>();

function verifyOnce(token: string) {
  const existing = verificationRequests.get(token);
  if (existing) {
    return existing;
  }
  const request = api<{ message: string }>("/auth/verify-email", {
    method: "POST",
    body: JSON.stringify({ token }),
  }).then((response) => response.message);
  verificationRequests.set(token, request);
  return request;
}

function VerifyEmailForm() {
  const params = useSearchParams();
  const [message, setMessage] = useState("Checking the verification link…");
  const [ok, setOk] = useState(false);

  useEffect(() => {
    const token = params.get("token");
    const url = new URL(window.location.href);
    url.searchParams.delete("token");
    window.history.replaceState({}, "", url.pathname);
    if (!token) {
      setMessage("This page needs a verification link from the API console.");
      return;
    }
    verifyOnce(token)
      .then((message) => {
        setOk(true);
        setMessage(message);
      })
      .catch((caught: unknown) => {
        setMessage(caught instanceof ApiError ? caught.message : "Verification failed.");
      });
  }, [params]);

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center px-4">
      <h1 className="text-3xl font-semibold">Email verification</h1>
      <p className={`mt-4 text-sm leading-6 ${ok ? "text-tide" : "text-mist"}`}>{message}</p>
      <Link href="/login" className="mt-6 text-sm text-tide">
        Go to sign in
      </Link>
    </main>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<main className="px-4 py-10 text-sm text-mist">Loading…</main>}>
      <VerifyEmailForm />
    </Suspense>
  );
}
