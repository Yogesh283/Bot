import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center bg-[#0b0e11] px-6 text-[#d1d4dc]">
      <p className="text-xs uppercase tracking-[0.18em] text-[#787b86]">MetaTrader 5</p>
      <h1 className="mt-3 text-4xl font-semibold tracking-tight">Trade</h1>
      <p className="mt-3 text-sm leading-6 text-[#787b86]">Sign in to the connected account.</p>
      <div className="mt-8 grid gap-3">
        <Link href="/login" className="rounded bg-[#2962ff] px-4 py-3 text-center font-semibold text-white">
          Sign in
        </Link>
        <Link href="/register" className="rounded border border-[#2a2e39] bg-[#131722] px-4 py-3 text-center font-semibold">
          Create account
        </Link>
      </div>
    </main>
  );
}
