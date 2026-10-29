import { readFileSync } from "fs";
import { resolve } from "path";

import type { NextConfig } from "next";

function loadRootEnv() {
  const file = resolve(__dirname, "../.env");
  let text = "";
  try {
    text = readFileSync(file, "utf8");
  } catch {
    return;
  }
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) {
      continue;
    }
    const eq = trimmed.indexOf("=");
    const key = trimmed.slice(0, eq).trim();
    let value = trimmed.slice(eq + 1).trim();
    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
      value = value.slice(1, -1);
    }
    if (process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

loadRootEnv();

const adminPath = (process.env.ADMIN_PATH || "xyz26").trim().replace(/^\/+|\/+$/g, "") || "xyz26";
const api = process.env.API_PROXY_TARGET || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  basePath: `/${adminPath}`,
  env: {
    NEXT_PUBLIC_ADMIN_PATH: `/${adminPath}`,
  },
  async rewrites() {
    return [{ source: "/backend/:path*", destination: `${api}/:path*` }];
  },
};

export default nextConfig;
