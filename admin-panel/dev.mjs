import { spawn } from "child_process";
import { readFileSync } from "fs";
import { dirname, resolve } from "path";
import { fileURLToPath } from "url";

const file = resolve(dirname(fileURLToPath(import.meta.url)), "../.env");
const text = readFileSync(file, "utf8");
for (const line of text.split(/\r?\n/)) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) {
    continue;
  }
  const eq = trimmed.indexOf("=");
  const key = trimmed.slice(0, eq).trim();
  let value = trimmed.slice(eq + 1).trim();
  if (process.env[key] === undefined) {
    process.env[key] = value;
  }
}

const domain = new URL(process.env.ADMIN_DOMAIN || "http://127.0.0.1:3001");
const port = domain.port || (domain.protocol === "https:" ? "443" : "80");
const child = spawn(
  "npx",
  ["next", "dev", "--hostname", domain.hostname, "--port", port],
  { stdio: "inherit", shell: true },
);
child.on("exit", (code) => process.exit(code ?? 0));
