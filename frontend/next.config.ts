import { readFileSync } from "fs";
import { resolve } from "path";

import type { NextConfig } from "next";

function loadRootEnv() {
  try {
    const text = readFileSync(resolve(__dirname, "../.env"), "utf8");
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
  } catch {
    return;
  }
}

loadRootEnv();

const nextConfig: NextConfig = {
  env: {
    NEXT_PUBLIC_USER_PANEL_URL: process.env.USER_PANEL_URL || process.env.APP_PUBLIC_URL || "",
  },
  async rewrites() {
    return [
      {
        source: "/backend/:path*",
        destination: `${process.env.API_PROXY_TARGET || "http://127.0.0.1:8000"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
