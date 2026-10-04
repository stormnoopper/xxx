"""Find candidate gambling URLs from search engines, public blocklists and CT logs."""

import base64
import html
import json
import re
import ssl
import sys
import time
import urllib.request
from urllib.parse import parse_qs, quote, urlsplit

from . import rules

BROWSER_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/128.0 Safari/537.36")
BING_RESULT = re.compile(r'<li class="b_algo".*?<h2[^>]*>\s*<a[^>]+href="([^"]+)"', re.S)


def _ctx() -> ssl.SSLContext:
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _get(url: str, timeout: float = 30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": BROWSER_UA, "Accept-Language": "th-TH,th;q=0.9"})
    with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
        return r.read().decode("utf-8", "replace")


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


def _decode_bing(href: str) -> str | None:
    """Bing wraps results as bing.com/ck/a?...&u=a1<base64url>."""
    href = html.unescape(href)
    if "bing.com/ck/a" not in href:
        return href
    u = parse_qs(urlsplit(href).query).get("u", [""])[0]
    if not u.startswith("a1"):
        return None
    s = u[2:] + "=" * (-len(u[2:]) % 4)
    try:
        return base64.urlsafe_b64decode(s).decode()
    except ValueError:
        return None


def from_search(queries: list[str], pages: int = 3, delay: float = 2.0) -> list[str]:
    found: list[str] = []
    for q in queries:
        before = len(found)
        for page in range(pages):
            try:
                body = _get(f"https://www.bing.com/search?q={quote(q)}&first={page * 10 + 1}&cc=TH&setlang=th")
            except Exception as e:
                _log(f"  bing '{q}' p{page + 1}: {type(e).__name__}: {e}")
                break
            urls = [u for u in (_decode_bing(m) for m in BING_RESULT.findall(body)) if u]
            found.extend(urls)
            time.sleep(delay)
            if not urls:
                break
        _log(f"  bing '{q}': {len(found) - before} results")
    return found


def from_blocklists(urls: list[str], pattern: re.Pattern = rules.THAI_BRAND_PATTERN) -> list[str]:
    found: list[str] = []
    for url in urls:
        try:
            body = _get(url, timeout=90)
        except Exception as e:
            _log(f"  blocklist {url}: {type(e).__name__}: {e}")
            continue
        domains = []
        for line in body.splitlines():
            d = line.strip().lstrip("*.").split("#")[0].strip()
            if " " in d:  # hosts-file format: "0.0.0.0 domain"
                d = d.split()[-1]
            if d and not d.startswith(("!", "[")) and pattern.search(d):
                domains.append(d)
        _log(f"  blocklist {urlsplit(url).netloc}: {len(domains)} Thai-brand domains")
        found.extend(domains)
    return found


def from_ct(keywords: list[str], retries: int = 3) -> list[str]:
    found: list[str] = []
    for kw in keywords:
        for attempt in range(retries):
            try:
                rows = json.loads(_get(f"https://crt.sh/?q=%25{quote(kw)}%25&output=json&exclude=expired", 90))
                names = {n.strip().lstrip("*.") for r in rows for n in r.get("name_value", "").splitlines()}
                found.extend(sorted(names))
                _log(f"  crt.sh '{kw}': {len(names)} names")
                break
            except Exception as e:
                _log(f"  crt.sh '{kw}' try {attempt + 1}: {type(e).__name__}: {e}")
                time.sleep(5)
    return found


def _ignored(host: str) -> bool:
    return any(host == h or host.endswith("." + h) for h in rules.IGNORE_HOSTS)


def dedupe(urls: list[str], per_host: int = 1) -> list[str]:
    """Keep at most `per_host` URLs per host; institution hosts keep their suspicious paths."""
    out, counts = [], {}
    for u in urls:
        u = u.strip()
        if not u:
            continue
        if "://" not in u:
            u = "https://" + u
        host = (urlsplit(u).hostname or "").lower()
        if not host or _ignored(host):
            continue
        limit = per_host * 5 if host.endswith(rules.INSTITUTION_SUFFIXES) else per_host
        if counts.get(host, 0) >= limit:
            continue
        counts[host] = counts.get(host, 0) + 1
        out.append(u)
    return out
