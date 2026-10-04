import { defang, loadSites, loadSummary } from "@/lib/results";
import { ResultsBrowser } from "./results-browser";

const SIGNS = [
  { title: "คำพนันในชื่อโดเมน", body: "bet, slot, casino, ufa, pg, vip ผสมเลข 168, 789, 888" },
  { title: "นามสกุลโดเมนราคาถูก", body: ".xyz .club .vip .top .online .site .icu" },
  { title: "เปลี่ยนโดเมนบ่อย", body: "ชื่อเดิมตามด้วย -2, -th, -net เพราะถูกบล็อก" },
  { title: "Subdomain หลายชั้น", body: "กระจายลิงก์หลายชั้นเพื่อหลบการบล็อก" },
  { title: "ลิงก์สั้น", body: "bit.ly, cutt.ly ที่ปลายทางเป็นเว็บพนัน" },
  { title: "เว็บที่ถูกแฮก", body: "/slot/ หรือ /?p=xxxx ซ่อนอยู่ในเว็บหน่วยงาน/โรงเรียน" },
];

const DATE_FMT = new Intl.DateTimeFormat("th-TH", { dateStyle: "long", timeZone: "Asia/Bangkok" });
const TIME_FMT = new Intl.DateTimeFormat("th-TH", { timeStyle: "short", timeZone: "Asia/Bangkok" });

export default function Home() {
  const sites = loadSites();
  const summary = loadSummary();
  const today = summary?.date ?? sites.map((s) => s.lastChecked).sort().at(-1) ?? "";
  const checkedAt = summary?.checked_at ? new Date(summary.checked_at) : null;
  const rows = sites.map((s) => ({
    ...s,
    display: defang(s.url.replace(/^https?:\/\//i, "").replace(/\/$/, "")),
    hiddenDisplay: s.hiddenLinks.map(defang),
  }));

  const active = sites.filter((s) => s.status === "active").length;
  const closed = sites.length - active;
  const kpis = [
    { label: "เปิดอยู่", value: active, accent: true },
    { label: "ปิดแล้ว", value: closed },
    { label: "พบใหม่รอบล่าสุด", value: sites.filter((s) => s.firstSeen === today && s.status === "active").length },
    { label: "ปิดรอบล่าสุด", value: sites.filter((s) => s.closedAt === today).length },
  ];

  return (
    <main className="mx-auto w-full max-w-5xl px-4 pb-20 sm:px-6">
      <header className="pt-14 pb-10 sm:pt-20">
        {checkedAt ? (
          <p className="flex flex-wrap items-baseline gap-x-2 text-sm">
            <span className="flex items-center gap-2 text-danger">
              <span className="size-1.5 translate-y-[-1px] rounded-full bg-danger" aria-hidden />
              ตรวจสอบล่าสุด
            </span>
            <time dateTime={summary!.checked_at} className="font-medium text-fg">
              {DATE_FMT.format(checkedAt)} · {TIME_FMT.format(checkedAt)} น.
            </time>
          </p>
        ) : (
          today && <p className="text-sm text-muted">ตรวจสอบล่าสุด {today}</p>
        )}
        <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-6xl">
          Thailand <span className="text-danger">-</span> Blackout
        </h1>
        <p className="mt-5 max-w-2xl text-lg leading-8 text-muted">
          รวมเว็บที่อาจจะเป็นเว็บพนันในประเทศไทย
          <br />
          <span className="text-fg">หาง่ายขนาดนี้ ทำไมรัฐบาลไม่จัดการ?</span>
        </p>
      </header>

      <section aria-label="สรุป" className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-4">
        {kpis.map((k) => (
          <div key={k.label} className="bg-surface p-4 sm:p-5">
            <p className="text-sm text-muted">{k.label}</p>
            <p className={`mt-1 text-3xl font-semibold tabular-nums ${k.accent ? "text-danger" : "text-fg"}`}>
              {k.value.toLocaleString()}
            </p>
          </div>
        ))}
      </section>

      <section className="mt-12">
        <h2 className="mb-4 text-xl font-semibold">รายชื่อเว็บ</h2>
        {sites.length ? (
          <ResultsBrowser rows={rows} today={today} />
        ) : (
          <p className="rounded-xl border border-dashed border-line p-8 text-center text-sm text-muted">
            ยังไม่มีข้อมูล — รัน <code className="font-mono">python3 -m gambling_bot update</code>
          </p>
        )}
      </section>

      <section className="mt-16">
        <h2 className="text-xl font-semibold">ลักษณะ URL เว็บพนันที่ควรระวัง</h2>
        <ol className="mt-5 grid gap-px overflow-hidden rounded-xl border border-line bg-line sm:grid-cols-2 lg:grid-cols-3">
          {SIGNS.map((s, i) => (
            <li key={s.title} className="bg-surface p-5">
              <span className="font-mono text-xs text-danger">{String(i + 1).padStart(2, "0")}</span>
              <p className="mt-2 font-medium">{s.title}</p>
              <p className="mt-1 text-sm leading-6 text-muted">{s.body}</p>
            </li>
          ))}
        </ol>
      </section>

      <footer className="mt-16 border-t border-line pt-6 text-xs leading-5 text-muted">
        &ldquo;ปิดแล้ว&rdquo; = ตรวจไม่พบติดกัน 2 รอบ (เปิดไม่ได้, HTTP 404/410/5xx หรือไม่มีเนื้อหาพนันแล้ว) ·
        ผลจาก heuristic score ควรตรวจซ้ำก่อนนำไปรายงาน
      </footer>
    </main>
  );
}
