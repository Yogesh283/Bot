export type BrokerServer = {
  broker: string;
  server: string;
  mode: "demo" | "live";
};

export const FALLBACK_BROKERS: BrokerServer[] = [
  { broker: "MetaQuotes", server: "MetaQuotes-Demo", mode: "demo" },
  { broker: "Exness", server: "Exness-MT5Trial", mode: "demo" },
  { broker: "Exness", server: "Exness-MT5Real", mode: "live" },
  { broker: "IC Markets", server: "ICMarketsSC-Demo", mode: "demo" },
  { broker: "IC Markets", server: "ICMarketsSC-MT5", mode: "live" },
  { broker: "Pepperstone", server: "Pepperstone-Demo", mode: "demo" },
  { broker: "Pepperstone", server: "Pepperstone-MT5-Live01", mode: "live" },
  { broker: "XM", server: "XMGlobal-MT5 2", mode: "demo" },
  { broker: "XM", server: "XMGlobal-MT5", mode: "live" },
  { broker: "FBS", server: "FBS-Demo", mode: "demo" },
  { broker: "FBS", server: "FBS-Real", mode: "live" },
  { broker: "RoboForex", server: "RoboForex-Pro", mode: "live" },
];

type RemoteBroker = {
  name?: string;
  servers?: { name?: string; type?: string }[];
};

export async function loadBrokers(): Promise<BrokerServer[]> {
  try {
    const response = await fetch("https://broker-servers.apis.tradevps.net/");
    if (!response.ok) {
      return FALLBACK_BROKERS;
    }
    const body = (await response.json()) as { brokers?: RemoteBroker[] };
    const rows: BrokerServer[] = [];
    for (const broker of body.brokers ?? []) {
      const name = broker.name?.trim();
      if (!name) {
        continue;
      }
      for (const server of broker.servers ?? []) {
        const serverName = server.name?.trim();
        if (!serverName) {
          continue;
        }
        const kind = (server.type || "").toLowerCase();
        rows.push({
          broker: name,
          server: serverName,
          mode: kind === "demo" || kind === "trial" ? "demo" : "live",
        });
      }
    }
    return rows.length ? rows : FALLBACK_BROKERS;
  } catch {
    return FALLBACK_BROKERS;
  }
}
