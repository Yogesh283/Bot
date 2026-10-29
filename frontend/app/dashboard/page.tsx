"use client";

import { useRouter } from "next/navigation";
import { FormEvent, useCallback, useEffect, useRef, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { useAuth } from "@/components/auth-provider";
import { ApiError, api } from "@/lib/api";
import { loadBrokers, type BrokerServer } from "@/lib/brokers";
import type { DashboardStatus } from "@/lib/types";

type Mt5Session = {
  stored: boolean;
  login: number | null;
  server: string | null;
  mode: "demo" | "live";
  connected: boolean;
};

function Mt5LoginForm() {
  const [mode, setMode] = useState<"demo" | "live">("demo");
  const [brokers, setBrokers] = useState<BrokerServer[]>([]);
  const [server, setServer] = useState("");
  const [customServer, setCustomServer] = useState("");
  const [loginId, setLoginId] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [session, setSession] = useState<Mt5Session | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let stopped = false;
    api<Mt5Session>("/mt5/session")
      .then((saved) => {
        if (stopped) {
          return;
        }
        setSession(saved);
        if (saved.mode === "live" || saved.mode === "demo") {
          setMode(saved.mode);
        }
        if (saved.server) {
          setServer(saved.server);
        }
        if (saved.login) {
          setLoginId(String(saved.login));
        }
      })
      .catch(() => {
        if (!stopped) {
          setError("The saved MT5 login could not be loaded.");
        }
      });
    return () => {
      stopped = true;
    };
  }, []);

  useEffect(() => {
    let stopped = false;
    loadBrokers().then((rows) => {
      if (!stopped) {
        setBrokers(rows);
      }
    });
    return () => {
      stopped = true;
    };
  }, []);

  const choices = brokers.filter((row) => row.mode === mode);
  const selectedServer = server === "other" ? customServer.trim() : server;

  async function connect(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const saved = await api<Mt5Session>("/mt5/session", {
        method: "POST",
        body: JSON.stringify({
          server: selectedServer,
          login: Number(loginId),
          password,
          mode,
        }),
      });
      setSession(saved);
      setPassword("");
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "MT5 login was not saved.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={connect} className="mb-4 rounded-lg border border-[#2a2e39] bg-[#131722] p-3 text-[#d1d4dc]">
      <div className="flex items-center justify-between gap-3">
        <p className="text-sm font-semibold">MT5 login</p>
        {session?.connected ? (
          <p className="text-xs font-semibold text-[#089981]">MT5 Connected</p>
        ) : (
          <p className="text-xs text-[#787b86]">Not connected</p>
        )}
      </div>
      {session?.connected ? (
        <p className="mt-1 text-xs text-[#787b86]">
          {session.server} · {session.login} · {session.mode === "live" ? "Live" : "Demo"}
        </p>
      ) : null}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <button type="button" onClick={() => { setMode("demo"); setServer(""); }} className={`h-10 rounded border text-sm ${mode === "demo" ? "border-[#089981] bg-[#089981] text-white" : "border-[#2a2e39]"}`}>
          Demo account
        </button>
        <button type="button" onClick={() => { setMode("live"); setServer(""); }} className={`h-10 rounded border text-sm ${mode === "live" ? "border-[#f23645] bg-[#f23645] text-white" : "border-[#2a2e39]"}`}>
          Live account
        </button>
      </div>
      <label className="mt-3 block text-[11px] uppercase text-[#787b86]">
        Broker
        <select aria-label="Broker" value={server} onChange={(event) => setServer(event.target.value)} className="mt-1 h-10 w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 text-sm text-[#d1d4dc]">
          <option value="">Choose a broker server</option>
          {choices.map((row) => (
            <option key={`${row.broker}-${row.server}`} value={row.server}>
              {row.broker} — {row.server}
            </option>
          ))}
          <option value="other">Other server</option>
        </select>
      </label>
      {server === "other" ? (
        <label className="mt-3 block text-[11px] uppercase text-[#787b86]">
          Server name
          <input aria-label="Server name" value={customServer} onChange={(event) => setCustomServer(event.target.value)} className="mt-1 h-10 w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 text-sm" />
        </label>
      ) : null}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <label className="text-[11px] uppercase text-[#787b86]">
          Login ID
          <input aria-label="Login ID" inputMode="numeric" value={loginId} onChange={(event) => setLoginId(event.target.value)} className="mt-1 h-10 w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 font-mono text-sm" />
        </label>
        <label className="text-[11px] uppercase text-[#787b86]">
          Password
          <span className="relative mt-1 block">
            <input aria-label="MT5 password" type={showPassword ? "text" : "password"} autoComplete="off" value={password} onChange={(event) => setPassword(event.target.value)} className="h-10 w-full rounded border border-[#2a2e39] bg-[#1e222d] px-2 pr-14 text-sm" />
            <button type="button" aria-label={showPassword ? "Hide password" : "Show password"} onClick={() => setShowPassword((current) => !current)} className="absolute right-2 top-1/2 -translate-y-1/2 text-xs text-[#787b86]">
              {showPassword ? "Hide" : "Show"}
            </button>
          </span>
        </label>
      </div>
      {error ? <p className="mt-3 text-sm text-[#f23645]">{error}</p> : null}
      <button type="submit" disabled={busy || !selectedServer || !loginId || !password} className="mt-3 h-11 w-full rounded bg-[#2962ff] text-sm font-semibold text-white disabled:opacity-50">
        {busy ? "Saving…" : "Connect MT5"}
      </button>
    </form>
  );
}

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
      <Mt5LoginForm />
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
