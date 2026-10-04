"""CLI entry point.

  python -m gambling_bot classify urls.txt          # offline, URL shape only
  python -m gambling_bot scan urls.txt -o out.csv    # fetch each URL and score
  python -m gambling_bot crawl https://school.ac.th --max-pages 50
      # crawl a (possibly hacked) site, report injected gambling pages/links
  python -m gambling_bot discover -o data/candidates.txt   # find candidate URLs
  python -m gambling_bot update                            # daily: discover + recheck registry
"""

import argparse
import csv
import json
import os
import sys
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urldefrag, urlsplit

from . import discover, registry
from .classifier import Verdict, host_of, normalize, score_url
from .fetcher import Fetcher, inspect

SKIP_EXT = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".pdf", ".zip", ".mp4",
            ".mp3", ".css", ".js", ".ico", ".doc", ".docx", ".xls", ".xlsx", ".rar")


def read_urls(path: str) -> list[str]:
    src = sys.stdin if path == "-" else open(path, encoding="utf-8")
    with src:
        return [ln.strip() for ln in src if ln.strip() and not ln.lstrip().startswith("#")]


def write_results(results: list[Verdict], out: str | None) -> None:
    rows = [r.to_dict() for r in results]
    if out:
        os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    if out and out.endswith(".json"):
        with open(out, "w", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
    elif out:
        with open(out, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["url"])
            w.writeheader()
            for r in rows:
                w.writerow({k: " | ".join(v) if isinstance(v, list) else v for k, v in r.items()})
    verbose = len(results) <= 50
    for r in results:
        if r.label != "CLEAN" or (r.error and verbose):
            print(f"[{r.label:8}] {r.score:3}  {r.url}" + (f"  -> {r.final_url}" if r.final_url and r.final_url != normalize(r.url) else "")
                  + (f"  ERROR {r.error}" if r.error else ""))
            for reason in r.reasons if verbose else []:
                print(f"            - {reason}")
            for h in r.hidden_links[:10] if verbose else []:
                print(f"            * hidden link: {h}")
    counts = {lbl: sum(r.label == lbl for r in results) for lbl in ("GAMBLING", "SUSPECT", "CLEAN")}
    print(f"\nTotal {len(results)} | " + " | ".join(f"{k} {v}" for k, v in counts.items())
          + (f" | saved -> {out}" if out else ""), file=sys.stderr)


def cmd_classify(args) -> list[Verdict]:
    return [score_url(u) for u in read_urls(args.input)]


def _inspect_many(urls: list[str], args) -> list[tuple[Verdict, object]]:
    """Fetch in parallel; each thread keeps its own Fetcher (per-thread delay)."""
    local = threading.local()

    def work(url):
        if not hasattr(local, "fetcher"):
            local.fetcher = Fetcher(args.timeout, args.delay, args.insecure)
        return inspect(url, local.fetcher)

    out = []
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futures = {ex.submit(work, u): u for u in urls}
        for i, fut in enumerate(as_completed(futures), 1):
            v, parser = fut.result()
            out.append((v, parser))
            state = "ERR " if v.error else f"{v.label[:4]} {v.score:3}"
            print(f"[{i}/{len(urls)}] {state}  {futures[fut]}", file=sys.stderr)
    return out


def scan_urls(urls: list[str], args) -> list[Verdict]:
    seen = {host_of(u) for u in urls}
    results: list[Verdict] = []
    for round_no in range(args.expand + 1):
        if not urls:
            break
        if round_no:
            print(f"\n== expand round {round_no}: {len(urls)} linked sites ==", file=sys.stderr)
        batch = _inspect_many(urls, args)
        results.extend(v for v, _ in batch)
        # Snowball: gambling pages link to sister brands / mirror domains.
        urls = []
        for v, parser in batch:
            if v.label != "GAMBLING" or not parser:
                continue
            for href, _hidden in parser.links:
                h = host_of(href)
                if h not in seen and score_url(href).label != "CLEAN":
                    seen.add(h)
                    urls.append(f"https://{h}/")
    return results


def cmd_scan(args) -> list[Verdict]:
    results = scan_urls(read_urls(args.input), args)
    if args.thai_only:
        results = [r for r in results if r.thai]
    if args.alive_only:
        results = [r for r in results if not r.error]
    if args.flagged_only:
        results = [r for r in results if r.label != "CLEAN"]
    return sorted(results, key=lambda r: -r.score)


def collect_candidates(args) -> list[str]:
    sources = set(args.sources.split(","))
    found: list[str] = []
    if "search" in sources:
        print("Searching Bing ...", file=sys.stderr)
        found += discover.from_search(discover.rules.SEARCH_QUERIES, pages=args.pages)
    if "blocklist" in sources:
        print("Reading public blocklists ...", file=sys.stderr)
        found += discover.from_blocklists(discover.rules.BLOCKLISTS)
    if "ct" in sources:
        print("Querying crt.sh ...", file=sys.stderr)
        found += discover.from_ct(discover.rules.CT_KEYWORDS)
    urls = discover.dedupe(found)
    print(f"{len(found)} raw -> {len(urls)} unique candidates", file=sys.stderr)
    return urls


def cmd_discover(args) -> None:
    urls = collect_candidates(args)
    if args.limit:
        urls = urls[: args.limit]
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write("\n".join(urls) + "\n")
    print(f"saved -> {args.out}", file=sys.stderr)


def cmd_update(args) -> None:
    """Daily job: recheck every known site, add newly discovered ones, mark closed ones."""
    rows = registry.load(args.registry)
    if not rows and args.seed and os.path.exists(args.seed):
        rows = registry.seed_from_results(args.seed, registry.today())
        print(f"Seeded registry with {len(rows)} sites from {args.seed}", file=sys.stderr)

    known = [r["url"] for r in rows.values()]
    fresh = [] if args.no_discover else collect_candidates(args)
    seen, urls = set(), []
    for u in known + fresh:
        k = registry.key(u)
        if k and k not in seen:
            seen.add(k)
            urls.append(u)
    print(f"Checking {len(known)} known + {len(urls) - len(known)} new candidates", file=sys.stderr)

    stats = registry.merge(rows, scan_urls(urls, args), close_after=args.close_after)
    registry.save(args.registry, rows)

    totals = {s: sum(r["status"] == s for r in rows.values()) for s in ("active", "closed")}
    summary = {"date": registry.today(), "checked_at": registry.now_iso(), "checked": len(urls), **stats, "total_active": totals["active"],
               "total_closed": totals["closed"], "total": len(rows)}
    with open(os.path.join(os.path.dirname(args.registry) or ".", "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print("\n" + json.dumps(summary, ensure_ascii=False), file=sys.stderr)


def cmd_crawl(args) -> list[Verdict]:
    """BFS within one host. Reports suspicious internal pages and outbound gambling links."""
    fetcher = Fetcher(args.timeout, args.delay, args.insecure)
    start = normalize(args.url)
    host = urlsplit(start).hostname
    queue, seen, results = deque([start]), {start}, []
    outbound: dict[str, Verdict] = {}

    while queue and len(results) < args.max_pages:
        url = queue.popleft()
        print(f"[{len(results) + 1}/{args.max_pages}] {url}", file=sys.stderr)
        v, parser = inspect(url, fetcher)
        results.append(v)
        if not parser:
            continue
        for href, hidden in parser.links:
            href = urldefrag(href)[0]
            h = urlsplit(href).hostname
            if h == host:
                if href not in seen and not urlsplit(href).path.lower().endswith(SKIP_EXT):
                    seen.add(href)
                    queue.append(href)
            elif href not in outbound:
                ov = score_url(href)
                if ov.label != "CLEAN" or hidden:
                    ov.reasons.append(f"found_on: {url}" + (" (hidden)" if hidden else ""))
                    outbound[href] = ov
    return results + [v for v in outbound.values() if v.label != "CLEAN"]


def main(argv=None) -> None:
    p = argparse.ArgumentParser(prog="gambling_bot", description="Detect gambling URLs / injected gambling links")
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, net=True):
        sp.add_argument("-o", "--out", help="output file (.csv or .json)")
        sp.add_argument("--all", action="store_true", help="include CLEAN rows in console output")
        if net:
            sp.add_argument("--timeout", type=float, default=10)
            sp.add_argument("--delay", type=float, default=1.0, help="seconds between requests")
            sp.add_argument("--insecure", action="store_true", help="skip TLS verification")

    sp = sub.add_parser("classify", help="score URLs by shape only (offline)")
    sp.add_argument("input", help="file with one URL per line, or - for stdin")
    common(sp, net=False)
    sp.set_defaults(func=cmd_classify)

    sp = sub.add_parser("scan", help="fetch each URL, resolve short links, score content")
    sp.add_argument("input")
    sp.add_argument("--workers", type=int, default=16, help="parallel fetches")
    sp.add_argument("--expand", type=int, default=0, help="rounds of following links from gambling pages")
    sp.add_argument("--thai-only", action="store_true", help="keep only results tagged as Thai market")
    sp.add_argument("--alive-only", action="store_true", help="drop URLs that could not be fetched")
    sp.add_argument("--flagged-only", action="store_true", help="drop CLEAN results")
    common(sp)
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("crawl", help="crawl one site to find injected gambling pages/links")
    sp.add_argument("url")
    sp.add_argument("--max-pages", type=int, default=50)
    common(sp)
    sp.set_defaults(func=cmd_crawl)

    sp = sub.add_parser("discover", help="collect candidate URLs from search / blocklists / crt.sh")
    sp.add_argument("-o", "--out", default="data/candidates.txt")
    sp.add_argument("--sources", default="search,blocklist", help="comma list: search,blocklist,ct")
    sp.add_argument("--pages", type=int, default=3, help="search result pages per query")
    sp.add_argument("--limit", type=int, default=0, help="max candidates (0 = all)")
    sp.set_defaults(func=cmd_discover)

    sp = sub.add_parser("update", help="daily run: discover + recheck registry, mark closed sites")
    sp.add_argument("--registry", default="data/sites.csv")
    sp.add_argument("--seed", default="data/results.csv", help="bootstrap registry from a scan CSV if empty")
    sp.add_argument("--close-after", type=int, default=2, help="consecutive failed checks before 'closed'")
    sp.add_argument("--no-discover", action="store_true", help="only recheck known sites")
    sp.add_argument("--sources", default="search,blocklist")
    sp.add_argument("--pages", type=int, default=2)
    sp.add_argument("--workers", type=int, default=32)
    sp.add_argument("--expand", type=int, default=1)
    sp.add_argument("--timeout", type=float, default=8)
    sp.add_argument("--delay", type=float, default=0)
    sp.add_argument("--insecure", action="store_true")
    sp.set_defaults(func=cmd_update)

    args = p.parse_args(argv)
    results = args.func(args)
    if results is None:
        return
    if args.all:
        for r in results:
            if r.label == "CLEAN" and not r.error:
                print(f"[CLEAN   ] {r.score:3}  {r.url}")
    write_results(results, args.out)
