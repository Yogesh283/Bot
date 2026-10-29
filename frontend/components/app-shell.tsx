"use client";

import { useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";

export function AppShell({ children }: { children: React.ReactNode }) {
  const { signOut } = useAuth();
  const router = useRouter();

  async function logout() {
    await signOut();
    router.replace("/login");
  }

  return (
    <div className="min-h-dvh bg-[#0b0e11]">
      <header className="border-b border-[#2a2e39] bg-[#131722] text-[#d1d4dc]">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-2">
          <p className="text-sm font-semibold">Trade</p>
          <button type="button" onClick={logout} className="text-xs text-[#787b86]">
            Sign out
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-3xl bg-[#0b0e11] px-4 py-4">{children}</main>
    </div>
  );
}
