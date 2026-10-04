"""Persistent site registry: tracks each gambling site across daily runs.

One row per host. Each run re-checks every known site plus newly discovered ones:
  - reachable and still gambling  -> status=active, last_seen=today
  - unreachable / gone            -> fail_count += 1; status=closed once fail_count >= close_after
  - closed site comes back        -> status=active again (reopened_at=today)
"""

import csv
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from .classifier import Verdict, host_of

TZ = ZoneInfo("Asia/Bangkok")

FIELDS = [
    "host", "url", "final_url", "status", "label", "score", "thai", "http_status",
    "first_seen", "last_seen", "last_checked", "closed_at", "reopened_at", "fail_count",
    "close_reason", "reasons", "hidden_links",
]

# HTTP codes that mean "site is gone" rather than "site blocks bots".
GONE_STATUS = {404, 410, 451}


def today() -> str:
    return datetime.now(TZ).date().isoformat()


def now_iso() -> str:
    return datetime.now(TZ).isoformat(timespec="minutes")


def key(url: str) -> str:
    return host_of(url).removeprefix("www.")


def load(path: str) -> dict[str, dict]:
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8-sig") as f:
        return {row["host"]: row for row in csv.DictReader(f)}


def save(path: str, rows: dict[str, dict]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    order = sorted(rows.values(), key=lambda r: (r["status"] != "active", -int(r["score"] or 0), r["host"]))
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(order)


def gone_reason(v: Verdict) -> str | None:
    """Why this check counts as 'not found', or None if the site is up and still gambling."""
    if v.error:
        return v.error.split(":")[0]  # e.g. URLError, TimeoutError
    if v.status in GONE_STATUS or (v.status or 0) >= 500:
        return f"HTTP {v.status}"
    if v.label == "CLEAN":
        return "no gambling content (parked / repurposed)"
    return None


def merge(rows: dict[str, dict], verdicts: list[Verdict], close_after: int = 2) -> dict[str, int]:
    """Apply today's verdicts to the registry in place. Returns change counts."""
    day = today()
    stats = {"new": 0, "active": 0, "closed_today": 0, "reopened": 0, "still_closed": 0, "failing": 0}

    for v in verdicts:
        k = key(v.url)
        row = rows.get(k)
        reason = gone_reason(v)

        if row is None:
            # Only reachable Thai gambling sites enter the registry.
            if reason or not v.thai:
                continue
            row = rows[k] = {"host": k, "first_seen": day, "fail_count": "0", "closed_at": "", "reopened_at": ""}
            stats["new"] += 1

        row["last_checked"] = day
        if reason is None:
            if row.get("status") == "closed":
                row["reopened_at"] = day
                stats["reopened"] += 1
            row.update({
                "url": v.url, "final_url": v.final_url or "", "status": "active", "label": v.label,
                "score": str(v.score), "thai": str(int(v.thai or row.get("thai") == "1")),
                "http_status": str(v.status or ""), "last_seen": day, "closed_at": "",
                "fail_count": "0", "close_reason": "",
                "reasons": " | ".join(v.reasons), "hidden_links": " | ".join(v.hidden_links),
            })
            stats["active"] += 1
        else:
            fails = int(row.get("fail_count") or 0) + 1
            row["fail_count"] = str(fails)
            row["close_reason"] = reason
            row["http_status"] = str(v.status or "")
            if row.get("status") == "closed":
                stats["still_closed"] += 1
            elif fails >= close_after:
                row["status"], row["closed_at"] = "closed", day
                stats["closed_today"] += 1
            else:
                stats["failing"] += 1  # first miss: keep active, confirm next run
    return stats


def seed_from_results(path: str, day: str) -> dict[str, dict]:
    """Bootstrap a registry from a previous `scan` CSV (all rows treated as active)."""
    rows: dict[str, dict] = {}
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            k = key(r["url"])
            rows[k] = {
                "host": k, "url": r["url"], "final_url": r["final_url"], "status": "active",
                "label": r["label"], "score": r["score"], "thai": r.get("thai", "1"),
                "http_status": r["status"], "first_seen": day, "last_seen": day, "last_checked": day,
                "closed_at": "", "reopened_at": "", "fail_count": "0", "close_reason": "",
                "reasons": r["reasons"], "hidden_links": r["hidden_links"],
            }
    return rows
