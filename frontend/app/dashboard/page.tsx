"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { ApiError, api } from "@/lib/api";
import type { DashboardStatus } from "@/lib/types";

function price(value: number | null | undefined) {
  return value == null ? "—" : value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

export default function DashboardPage() {
  const { user, ready } = useAuth();
  const router = useRouter();
  const [status, setStatus] = useState<DashboardStatus | null>(null);
  const [error, setError] = useState("");
  const [symbol, setSymbol] = useState("XAUUSD");
  const [lot, setLot] = useState("0.01");
  const [stopLoss, setStopLoss] = useState("300");
  const [takeProfit, setTakeProfit] = useState("600");
  const [busy, setBusy] = useState(false);
  const formReady = useRef(false);

  const load = useCallback(async () => {
    const next = await api<DashboardStatus>("/dashboard/status");
    setStatus(next);
    if (!formReady.current) {
      setSymbol(next.symbol);
      setLot(String(next.lot_size ?? 0.01));
      setStopLoss(String(next.stop_loss_points ?? 300));
      setTakeProfit(String(next.take_profit_points ?? 600));
      formReady.current = true;
    }
  }, []);

  useEffect(() => {
    if (ready && !user) {
      router.replace("/login");
    }
  }, [ready, user, router]);

  useEffect(() => {
    if (!user) {
      return;
    }
    let stopped = false;
    const tick = () => {
      load()
        .then(() => {
          if (!stopped) {
            setError("");
          }
        })
        .catch(() => {
          if (!stopped) {
            setError("Sign in again if the screen could not load.");
          }
        });
    };
    tick();
    const timer = window.setInterval(tick, 5000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [user, load]);

  async function send(side: "BUY" | "SELL") {
    setBusy(true);
    setError("");
    try {
      await api("/bot/settings", {
        method: "POST",
        body: JSON.stringify({
          symbol,
          lot_size: Number(lot),
          stop_loss_points: Number(stopLoss),
          take_profit_points: Number(takeProfit),
        }),
      });
      const result = await api<{ queued: boolean; error?: string | null }>("/bot/demo-order", {
        method: "POST",
        body: JSON.stringify({ side, confirm: "DEMO" }),
      });
      if (!result.queued) {
        throw new ApiError(409, result.error || "The order was not sent.");
      }
      await load();
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The order was not sent.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AppShell>
      <section data-screen="mt5-trade" className="overflow-hidden rounded-lg border border-[#2a2e39] bg-[#131722] text-[#d1d4dc]">
        <div className="flex items-center gap-3 border-b border-[#2a2e39] px-3 py-3">
          <input
            aria-label="Symbol"
            value={symbol}
            onChange={(event) => setSymbol(event.target.value.toUpperCase())}
            className="w-28 bg-transparent font-mono text-lg font-semibold outline-none"
          />
          <p className="font-mono text-xl text-[#f23645]">{price(status?.bid)}</p>
          <p className="font-mono text-xl text-[#089981]">{price(status?.ask)}</p>
          <p className="ml-auto text-xs uppercase tracking-wide text-[#787b86]">{status?.environment === "live" ? "Live" : "Demo"}</p>
        </div>
        <div className="grid grid-cols-3 gap-2 px-3 py-3">
          <label className="text-[11px] uppercase text-[#787b86]">
            Lot
            <input aria-label="Lot" value={lot} onChange={(event) => setLot(event.target.value)} className="mt-1 h-10 w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 font-mono text-sm text-[#d1d4dc]" />
          </label>
          <label className="text-[11px] uppercase text-[#787b86]">
            Stop loss
            <input aria-label="Stop loss" value={stopLoss} onChange={(event) => setStopLoss(event.target.value)} className="mt-1 h-10 w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 font-mono text-sm text-[#d1d4dc]" />
          </label>
          <label className="text-[11px] uppercase text-[#787b86]">
            Take profit
            <input aria-label="Take profit" value={takeProfit} onChange={(event) => setTakeProfit(event.target.value)} className="mt-1 h-10 w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 font-mono text-sm text-[#d1d4dc]" />
          </label>
        </div>
        <div className="grid grid-cols-2 gap-2 px-3 pb-3">
          <button type="button" disabled={busy} onClick={() => send("SELL")} className="h-12 rounded bg-[#f23645] text-base font-semibold text-white disabled:opacity-50">
            Sell
          </button>
          <button type="button" disabled={busy} onClick={() => send("BUY")} className="h-12 rounded bg-[#089981] text-base font-semibold text-white disabled:opacity-50">
            Buy
          </button>
        </div>
        {error ? <p className="px-3 pb-3 text-sm text-[#f23645]">{error}</p> : null}
        <table className="w-full border-t border-[#2a2e39] text-left text-sm">
          <thead className="text-[11px] uppercase text-[#787b86]">
            <tr>
              <th className="px-3 py-2 font-medium">Symbol</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Volume</th>
              <th className="px-3 py-2 text-right font-medium">Profit</th>
            </tr>
          </thead>
          <tbody>
            {status?.open_positions?.length ? (
              status.open_positions.map((position) => (
                <tr key={position.ticket} className="border-t border-[#2a2e39] font-mono">
                  <td className="px-3 py-2">{position.symbol}</td>
                  <td className="px-3 py-2">{position.side}</td>
                  <td className="px-3 py-2">{position.volume}</td>
                  <td className={`px-3 py-2 text-right ${position.profit < 0 ? "text-[#f23645]" : "text-[#089981]"}`}>{price(position.profit)}</td>
                </tr>
              ))
            ) : (
              <tr>
                <td className="px-3 py-4 text-[#787b86]" colSpan={4}>
                  No open positions
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </section>
    </AppShell>
  );
}
