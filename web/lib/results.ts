import { readFileSync } from "node:fs";
import path from "node:path";

export type Label = "GAMBLING" | "SUSPECT" | "CLEAN";
export type Status = "active" | "closed";

export type Site = {
  host: string;
  url: string;
  status: Status;
  label: Label;
  score: number;
  httpStatus: string;
  firstSeen: string;
  lastSeen: string;
  lastChecked: string;
  closedAt: string;
  reopenedAt: string;
  failCount: number;
  closeReason: string;
  reasons: { rule: string; detail: string }[];
  hiddenLinks: string[];
};

export type Summary = {
  date: string;
  checked_at?: string; // ISO datetime, Asia/Bangkok
  checked: number;
  new: number;
  closed_today: number;
  reopened: number;
  total_active: number;
  total_closed: number;
};

// Bot output lives at <repo>/data/; override with DATA_DIR.
const DATA_DIR = process.env.DATA_DIR ?? path.join(/* turbopackIgnore: true */ process.cwd(), "..", "data");

/** Minimal RFC 4180 parser: quoted fields, escaped quotes, newlines inside quotes. */
function parseCsv(text: string): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let quoted = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++; }
      else if (c === '"') quoted = false;
      else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); rows.push(row); row = []; field = "";
    } else field += c;
  }
  if (field || row.length) { row.push(field); rows.push(row); }
  return rows.filter((r) => r.some(Boolean));
}

const split = (s: string) => (s ? s.split(" | ").filter(Boolean) : []);

function read(file: string): string | null {
  try {
    return readFileSync(path.join(DATA_DIR, file), "utf-8").replace(/^﻿/, "");
  } catch {
    return null;
  }
}

export function loadSites(): Site[] {
  const text = read("sites.csv");
  if (!text) return [];
  const [header, ...rows] = parseCsv(text);
  if (!header) return [];
  return rows
    .map((cells) => Object.fromEntries(header.map((h, i) => [h, cells[i] ?? ""])))
    .map((r) => ({
      host: r.host,
      url: r.url,
      status: (r.status || "active") as Status,
      label: (r.label || "CLEAN") as Label,
      score: Number(r.score) || 0,
      httpStatus: r.http_status,
      firstSeen: r.first_seen,
      lastSeen: r.last_seen,
      lastChecked: r.last_checked,
      closedAt: r.closed_at,
      reopenedAt: r.reopened_at,
      failCount: Number(r.fail_count) || 0,
      closeReason: r.close_reason,
      reasons: split(r.reasons).map((x) => {
        const i = x.indexOf(": ");
        return i < 0 ? { rule: x, detail: "" } : { rule: x.slice(0, i), detail: x.slice(i + 2) };
      }),
      hiddenLinks: split(r.hidden_links),
    }));
}

export function loadSummary(): Summary | null {
  const text = read("summary.json");
  return text ? (JSON.parse(text) as Summary) : null;
}

/** Make a URL non-clickable and non-auto-linkable: ufabet168.xyz -> ufabet168[.]xyz */
export function defang(url: string): string {
  return url.replace(/^http(s?):\/\//i, "hxxp$1://").replace(/\./g, "[.]");
}
