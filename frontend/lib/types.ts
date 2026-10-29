export type Role = "user" | "admin";

export type User = {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  email_verified: boolean;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
  expires_in: number;
};

export type AnalysisView = {
  signal: "BUY" | "SELL" | "NO_SIGNAL" | null;
  symbol: string | null;
  timeframe: string | null;
  candle_time: string | null;
  fast_ma: number | null;
  slow_ma: number | null;
  data_status: "ok" | "missing" | "stale" | "invalid" | null;
  detail: string | null;
};

export type PositionView = {
  ticket: number;
  symbol: string;
  side: string;
  volume: number;
  price_open: number;
  sl: number | null;
  tp: number | null;
  profit: number;
};

export type OrderView = {
  id: string;
  symbol: string;
  side: string;
  volume: number;
  sl: number | null;
  tp: number | null;
  status: string;
  retcode: number | null;
  order_ticket: number | null;
  deal_ticket: number | null;
  error: string | null;
  created_at: string;
};

export type DashboardStatus = {
  agent_status: "offline" | "online";
  mt5_status: "not_configured" | "connected" | "setup_required" | "live_rejected";
  bot_status: "stopped" | "running";
  environment: "demo" | "live";
  bid: number | null;
  ask: number | null;
  lot_size: number;
  stop_loss_points: number;
  take_profit_points: number;
  balance: number | null;
  equity: number | null;
  floating_pnl: number | null;
  daily_pnl: number | null;
  open_positions: PositionView[];
  closed_trades: OrderView[];
  orders: OrderView[];
  notifications: string[];
  trading_enabled: true;
  demo_trading_enabled: boolean;
  setup_requirement: string | null;
  symbol: string;
  timeframe: string;
  subscription?: {
    plan: string;
    status: "active" | "expired" | "cancelled" | "none";
    expires_at: string | null;
  };
  accuracy?: {
    closed_trades: number;
    wins: number;
    accuracy: number | null;
  };
  account_link?: {
    deposit_inr: number;
    deposit_status: "pending" | "confirmed";
    broker_confirmed: boolean;
    broker_server: string | null;
    broker_login: number | null;
    broker_mobile: string | null;
    vpn_username: string | null;
    vps_username: string | null;
    execution: "waiting" | "linked";
  };
  analysis: AnalysisView | null;
};

export type AdminSignalSummary = {
  id: string;
  symbol: string;
  side: string;
  tp_mode: string;
  created_at: string;
  recipients: number;
  counts: Record<string, number>;
};

export type Activity = {
  id: string;
  action: string;
  detail: string;
  ip_address: string | null;
  created_at: string;
  user_id: string | null;
};

export type HealthReport = {
  api: "ok";
  database: "ok" | "unavailable";
  redis: "ok" | "unavailable";
  phase: 1;
  trading_enabled: true;
};
