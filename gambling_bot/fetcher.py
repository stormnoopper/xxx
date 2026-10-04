"""Network side: follow redirects, read page, extract links and hidden-link injections."""

import ssl
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

from . import rules
from .classifier import Verdict, normalize, score_url

USER_AGENT = "Mozilla/5.0 (compatible; GamblingLinkAuditBot/1.0)"
MAX_BYTES = 2_000_000
# SPA gambling sites often carry their keywords only in <title>/meta.
META_TEXT = {"description", "keywords", "og:title", "og:description", "twitter:title"}
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
             "meta", "source", "track", "wbr"}


class _RecordingRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self):
        self.chain: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class LinkParser(HTMLParser):
    """Collect <a href> links, flagging those inside a hidden ancestor."""

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.links: list[tuple[str, bool]] = []
        self.text_parts: list[str] = []
        self._stack: list[bool] = []  # hidden flag per open element
        self._skip_text = 0

    def _hidden(self) -> bool:
        return any(self._stack)

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        style = a.get("style") or ""
        hidden = bool(rules.HIDDEN_STYLE_PATTERN.search(style)) or "hidden" in a
        if tag in ("script", "style", "noscript"):
            self._skip_text += 1
        if tag == "meta" and (a.get("name") or a.get("property") or "").lower() in META_TEXT:
            self.text_parts.append(a.get("content") or "")
        if tag == "a" and a.get("href"):
            href = urljoin(self.base_url, a["href"])
            if href.startswith(("http://", "https://")):
                self.links.append((href, self._hidden() or hidden))
        if tag not in VOID_TAGS:
            self._stack.append(hidden)

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip_text = max(0, self._skip_text - 1)
        if tag not in VOID_TAGS and self._stack:
            self._stack.pop()

    def handle_data(self, data):
        if not self._skip_text:
            self.text_parts.append(data)


class Fetcher:
    def __init__(self, timeout: float = 10, delay: float = 1.0, insecure: bool = False):
        self.timeout = timeout
        self.delay = delay
        self._last = 0.0
        try:  # python.org macOS builds ship without a CA bundle
            import certifi
            self.ctx = ssl.create_default_context(cafile=certifi.where())
        except ImportError:
            self.ctx = ssl.create_default_context()
        if insecure:
            self.ctx.check_hostname = False
            self.ctx.verify_mode = ssl.CERT_NONE

    def get(self, url: str) -> tuple[int | None, str, str, list[str]]:
        """Return (status, final_url, html, redirect_chain)."""
        wait = self.delay - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()

        redirect = _RecordingRedirect()
        opener = urllib.request.build_opener(redirect, urllib.request.HTTPSHandler(context=self.ctx))
        req = urllib.request.Request(normalize(url), headers={
            "User-Agent": USER_AGENT, "Accept-Language": "th,en;q=0.8"})
        try:
            with opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read(MAX_BYTES)
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.status, resp.geturl(), raw.decode(charset, "replace"), redirect.chain
        except urllib.error.HTTPError as e:
            body = e.read(MAX_BYTES).decode("utf-8", "replace") if e.fp else ""
            return e.code, e.geturl() or url, body, redirect.chain


def analyze_content(html: str, base_url: str, v: Verdict) -> LinkParser:
    parser = LinkParser(base_url)
    try:
        parser.feed(html)
    except Exception:  # malformed HTML must not kill the scan
        pass

    text = " ".join(parser.text_parts).lower()
    hits = [k for k in rules.CONTENT_KEYWORDS if k.lower() in text]
    if any(rules.THAI_CHARS.search(k) for k in hits):
        v.thai = True
    if rules.CHALLENGE_PATTERN.search(html[:20000]):
        v.reasons.append("bot_challenge: page behind Cloudflare/JS challenge, content not checked")
    if hits:
        weight = min(len(hits) * rules.WEIGHTS["content_keyword"], rules.WEIGHTS["content_keyword_cap"])
        v.add("content_keyword", ",".join(hits[:10]), weight)

    base_host = urlsplit(base_url).hostname
    for href, hidden in parser.links:
        if not hidden or urlsplit(href).hostname == base_host:
            continue
        if score_url(href).label != "CLEAN":
            v.hidden_links.append(href)
    if v.hidden_links:
        v.add("hidden_gambling_link", f"{len(v.hidden_links)} link(s)")
    return parser


def inspect(url: str, fetcher: Fetcher) -> tuple[Verdict, LinkParser | None]:
    """Full check: URL shape + resolve redirects/short links + page content."""
    v = score_url(url)
    try:
        status, final_url, html, chain = fetcher.get(url)
    except Exception as e:
        v.error = f"{type(e).__name__}: {e}"
        return v, None

    v.status, v.final_url = status, final_url
    if chain:
        v.reasons.append(f"redirects: {' -> '.join(chain[:5])}")
    if urlsplit(final_url).hostname != urlsplit(normalize(url)).hostname:
        # Short links / domain hops: judge by whichever shape is stronger, never both.
        dest = score_url(final_url)
        if dest.score > v.score:
            v.score = dest.score
            v.reasons = [r for r in v.reasons if r.startswith("redirects:")] + dest.reasons
            v.thai = v.thai or dest.thai

    return v, analyze_content(html, final_url, v)
