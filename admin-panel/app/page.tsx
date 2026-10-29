"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { ApiError, api, getToken, setToken } from "@/lib/api";

type Result = { account: string; status: string; detail: string };
type Copy = { symbol: string; side: string; lot: number; queued: number; results: Result[] };

export default function DeskPage() {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  const [username, setUsername] = useState("");
  const [symbol, setSymbol] = useState("XAUUSD");
  const [lot, setLot] = useState("0.01");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [copy, setCopy] = useState<Copy | null>(null);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    api<{ username: string }>("/control/me")
      .then((body) => {
        setUsername(body.username);
        setReady(true);
      })
      .catch(() => {
        setToken(null);
        router.replace("/login");
      });
  }, [router]);

  async function send(side: "BUY" | "SELL") {
    setBusy(true);
    setError("");
    try {
      const body = await api<Copy>("/control/trades", {
        method: "POST",
        body: JSON.stringify({ symbol, side, lot: Number(lot) }),
      });
      setCopy(body);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The trade was not copied.");
    } finally {
      setBusy(false);
    }
  }

  if (!ready) {
    return <main className="p-8 text-sm text-[#5c6b7a]">Loading the desk…</main>;
  }

  return (
    <div className="grid min-h-dvh grid-cols-[220px_1fr]">
      <aside className="border-r border-[#10263c] bg-[#16324f] px-5 py-6 text-white">
        <p className="text-xs uppercase tracking-[0.16em] text-[#b7c6d6]">Admin desk</p>
        <p className="mt-3 text-lg font-semibold">{username}</p>
        <nav className="mt-8 text-sm">
          <p className="rounded bg-white/10 px-3 py-2">Trade copy</p>
        </nav>
        <button
          type="button"
          className="mt-8 text-sm text-[#b7c6d6]"
          onClick={() => {
            setToken(null);
            router.replace("/login");
          }}
        >
          Sign out
        </button>
      </aside>
      <main className="px-6 py-8">
        <h1 className="text-2xl font-semibold">Copy a trade</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-[#5c6b7a]">
          One order is copied to every connected terminal with this symbol, side, and lot. A terminal that is offline, or has no quote for the symbol, is skipped.
        </p>
        <section className="mt-6 max-w-3xl rounded-lg border border-[#d7dee7] bg-white p-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-medium">
              Symbol
              <input value={symbol} onChange={(event) => setSymbol(event.target.value.toUpperCase())} className="mt-1 h-11 w-full rounded border border-[#c5ced8] px-3 font-mono" />
            </label>
            <label className="text-sm font-medium">
              Lot
              <input value={lot} onChange={(event) => setLot(event.target.value)} className="mt-1 h-11 w-full rounded border border-[#c5ced8] px-3 font-mono" />
            </label>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3">
            <button type="button" disabled={busy} onClick={() => send("SELL")} className="h-11 rounded bg-[#b42318] font-semibold text-white disabled:opacity-60">
              Sell
            </button>
            <button type="button" disabled={busy} onClick={() => send("BUY")} className="h-11 rounded bg-[#067647] font-semibold text-white disabled:opacity-60">
              Buy
            </button>
          </div>
          {error ? <p className="mt-3 text-sm text-[#b42318]">{error}</p> : null}
        </section>
        {copy ? (
          <section className="mt-6 max-w-3xl overflow-hidden rounded-lg border border-[#d7dee7] bg-white">
            <p className="border-b border-[#d7dee7] px-5 py-3 text-sm">
              {copy.side} {copy.symbol} {copy.lot} · queued {copy.queued}
            </p>
            <table className="w-full text-left text-sm">
              <thead className="text-xs uppercase text-[#5c6b7a]">
                <tr>
                  <th className="px-5 py-2 font-medium">Account</th>
                  <th className="px-5 py-2 font-medium">Status</th>
                  <th className="px-5 py-2 font-medium">Detail</th>
                </tr>
              </thead>
              <tbody>
                {copy.results.map((row) => (
                  <tr key={row.account} className="border-t border-[#e6edf3]">
                    <td className="px-5 py-2">{row.account}</td>
                    <td className="px-5 py-2">{row.status}</td>
                    <td className="px-5 py-2">{row.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        ) : null}
      </main>
    </div>
  );
}
