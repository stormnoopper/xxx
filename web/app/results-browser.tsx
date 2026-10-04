"use client";

import { useState } from "react";
import type { Site } from "@/lib/results";

type Row = Site & { display: string; hiddenDisplay: string[] };
type Filter = "all" | "active" | "closed" | "new" | "closed_today";

const PAGE = 100;

const RULE_TEXT: Record<string, string> = {
  strong_keyword: "คำพนันในโดเมน",
  weak_keyword_combo: "คำกว้าง + ตัวเลข",
  number_pattern: "เลขนิยม",
  cheap_tld: "TLD ราคาถูก",
  rotation_suffix: "โดเมนหมุนเวียน",
  deep_subdomain: "Subdomain หลายชั้น",
  shortener: "ลิงก์สั้น",
  suspicious_path_on_institution: "Path ต้องสงสัยบนเว็บหน่วยงาน",
  suspicious_path: "Path ต้องสงสัย",
  content_keyword: "คำพนันในเนื้อหา",
  hidden_gambling_link: "ลิงก์ซ่อน",
  bot_challenge: "ติด Cloudflare",
  redirects: "Redirect",
  found_on: "พบที่",
};

export function ResultsBrowser({ rows, today }: { rows: Row[]; today: string }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  const [shown, setShown] = useState(PAGE);

  const filters: { key: Filter; text: string; test: (r: Row) => boolean }[] = [
    { key: "all", text: "ทั้งหมด", test: () => true },
    { key: "active", text: "เปิดอยู่", test: (r) => r.status === "active" },
    { key: "closed", text: "ปิดแล้ว", test: (r) => r.status === "closed" },
    { key: "new", text: "พบใหม่รอบล่าสุด", test: (r) => r.firstSeen === today && r.status === "active" },
    { key: "closed_today", text: "ปิดรอบล่าสุด", test: (r) => r.closedAt === today },
  ];
  const current = filters.find((f) => f.key === filter)!;

  const q = query.trim().toLowerCase();
  const visible = rows.filter((r) => current.test(r) && (!q || r.host.includes(q)));

  const reset = () => setShown(PAGE);

  return (
    <div>
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap gap-2" role="tablist">
          {filters.map((f) => {
            const active = filter === f.key;
            return (
              <button
                key={f.key}
                role="tab"
                aria-selected={active}
                onClick={() => { setFilter(f.key); reset(); }}
                className={`rounded-full border px-3.5 py-1.5 text-sm transition-colors ${
                  active ? "border-fg bg-fg text-bg" : "border-line text-muted hover:border-fg hover:text-fg"
                }`}
              >
                {f.text} <span className="tabular-nums opacity-70">{rows.filter(f.test).length}</span>
              </button>
            );
          })}
        </div>
        <input
          type="search"
          value={query}
          onChange={(e) => { setQuery(e.target.value); reset(); }}
          placeholder="ค้นหาโดเมน…"
          className="w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-fg outline-none placeholder:text-muted focus:border-fg lg:w-64"
        />
      </div>

      <ul className="mt-5 divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface">
        {visible.length === 0 && (
          <li className="px-5 py-10 text-center text-sm text-muted">ไม่พบรายการที่ตรงเงื่อนไข</li>
        )}
        {visible.slice(0, shown).map((r) => {
          const expanded = open === r.host;
          const closed = r.status === "closed";
          return (
            <li key={r.host}>
              <button
                onClick={() => setOpen(expanded ? null : r.host)}
                aria-expanded={expanded}
                className="grid w-full grid-cols-[1fr_auto] items-center gap-x-4 gap-y-2 px-4 py-3.5 text-left hover:bg-hover sm:grid-cols-[6.5rem_1fr_7rem_8rem] sm:px-5"
              >
                <StatusBadge row={r} today={today} />
                <span className="col-span-2 min-w-0 sm:col-span-1">
                  <span className={`block truncate font-mono text-sm ${closed ? "text-muted line-through decoration-line" : ""}`}>
                    {r.display}
                  </span>
                  <span className="mt-0.5 block truncate text-xs text-muted">
                    {r.reasons.filter((x) => x.rule !== "redirects").map((x) => RULE_TEXT[x.rule] ?? x.rule).join(" · ") || "—"}
                  </span>
                </span>
                <ScoreBar score={r.score} dim={closed} />
                <span className="hidden text-right text-xs leading-5 text-muted sm:block">
                  {closed ? <>ปิด {r.closedAt}</> : <>พบล่าสุด {r.lastSeen}</>}
                  <br />
                  <span className="opacity-70">พบครั้งแรก {r.firstSeen}</span>
                </span>
              </button>
              {expanded && <Detail row={r} />}
            </li>
          );
        })}
      </ul>
      {visible.length > shown && (
        <button
          onClick={() => setShown((n) => n + PAGE)}
          className="mt-4 w-full rounded-lg border border-line py-2.5 text-sm text-muted hover:border-fg hover:text-fg"
        >
          แสดงเพิ่ม ({visible.length - shown} รายการ)
        </button>
      )}
    </div>
  );
}

function Detail({ row }: { row: Row }) {
  const timeline: [string, string][] = [
    ["พบครั้งแรก", row.firstSeen],
    ["พบล่าสุด (เปิดอยู่)", row.lastSeen],
    ["ตรวจล่าสุด", row.lastChecked],
  ];
  if (row.closedAt) timeline.push(["ปิดเมื่อ", row.closedAt]);
  if (row.reopenedAt) timeline.push(["กลับมาเปิดเมื่อ", row.reopenedAt]);
  if (row.closeReason) timeline.push([row.status === "closed" ? "สาเหตุที่ปิด" : `ตรวจไม่พบ ${row.failCount} ครั้ง`, row.closeReason]);

  return (
    <div className="grid gap-6 border-t border-line bg-hover px-4 py-4 text-sm sm:grid-cols-2 sm:px-5">
      <dl className="grid grid-cols-[8.5rem_1fr] content-start gap-x-4 gap-y-2">
        {timeline.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd className="break-all font-mono text-xs leading-5">{v || "—"}</dd>
          </div>
        ))}
      </dl>
      <dl className="grid grid-cols-[8.5rem_1fr] content-start gap-x-4 gap-y-2">
        {row.reasons.map((x, i) => (
          <div key={i} className="contents">
            <dt className="text-muted">{RULE_TEXT[x.rule] ?? x.rule}</dt>
            <dd className="break-all font-mono text-xs leading-5">{x.detail || "—"}</dd>
          </div>
        ))}
        {row.hiddenDisplay.length > 0 && (
          <div className="contents">
            <dt className="text-muted">ลิงก์ที่ซ่อน</dt>
            <dd className="space-y-1 break-all font-mono text-xs leading-5">
              {row.hiddenDisplay.slice(0, 10).map((h) => <div key={h}>{h}</div>)}
            </dd>
          </div>
        )}
      </dl>
    </div>
  );
}

function StatusBadge({ row, today }: { row: Row; today: string }) {
  if (row.status === "closed") {
    return <span className="w-fit rounded-md border border-line px-2 py-0.5 text-xs text-muted">ปิดแล้ว</span>;
  }
  const isNew = row.firstSeen === today;
  return (
    <span className="flex w-fit items-center gap-1.5 rounded-md bg-danger-soft px-2 py-0.5 text-xs font-medium text-danger">
      <span className="size-1.5 rounded-full bg-danger" aria-hidden />
      {isNew ? "ใหม่" : "เปิดอยู่"}
    </span>
  );
}

function ScoreBar({ score, dim }: { score: number; dim: boolean }) {
  return (
    <span className="flex items-center gap-2 sm:justify-end" title={`score ${score}`}>
      <span className="h-1 w-14 overflow-hidden rounded-full bg-line">
        <span className={`block h-full ${dim ? "bg-muted" : "bg-danger"}`} style={{ width: `${Math.min(score, 100)}%` }} />
      </span>
      <span className="w-7 text-right text-xs tabular-nums text-muted">{score}</span>
    </span>
  );
}
