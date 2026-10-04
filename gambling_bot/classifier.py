"""Static URL scoring (no network)."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from urllib.parse import urlsplit

from . import rules


@dataclass
class Verdict:
    url: str
    score: int = 0
    reasons: list[str] = field(default_factory=list)
    final_url: str | None = None
    status: int | None = None
    error: str | None = None
    hidden_links: list[str] = field(default_factory=list)
    thai: bool = False
    scanned_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"))

    @property
    def label(self) -> str:
        if self.score >= rules.THRESHOLD_GAMBLING:
            return "GAMBLING"
        if self.score >= rules.THRESHOLD_SUSPECT:
            return "SUSPECT"
        return "CLEAN"

    def add(self, key: str, detail: str, weight: int | None = None) -> None:
        self.score += rules.WEIGHTS[key] if weight is None else weight
        self.reasons.append(f"{key}: {detail}")

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "host": host_of(self.final_url or self.url),
            "final_url": self.final_url,
            "label": self.label,
            "score": self.score,
            "status": self.status,
            "reasons": self.reasons,
            "hidden_links": self.hidden_links,
            "thai": int(self.thai),
            "error": self.error,
            "scanned_at": self.scanned_at,
        }


def normalize(url: str) -> str:
    url = url.strip()
    if "://" not in url:
        url = "http://" + url
    return url


def host_of(url: str) -> str:
    return (urlsplit(normalize(url)).hostname or "").lower()


def is_shortener(url: str) -> bool:
    host = host_of(url)
    return host in rules.URL_SHORTENERS or host.removeprefix("www.") in rules.URL_SHORTENERS


def is_institution(host: str) -> bool:
    return host.endswith(rules.INSTITUTION_SUFFIXES)


def score_url(url: str, verdict: Verdict | None = None) -> Verdict:
    """Score a URL from its shape only. Pass an existing verdict to accumulate."""
    v = verdict or Verdict(url=url)
    parts = urlsplit(normalize(url))
    host = (parts.hostname or "").lower()
    path_q = parts.path + ("?" + parts.query if parts.query else "")

    if is_shortener(url):
        v.add("shortener", host)
        return v  # shape of a short link says nothing; resolve it first

    labels = host.removeprefix("www.").split(".")
    tld = labels[-1] if labels else ""
    # Registrable name ~ second-level label (good enough without a PSL dependency).
    name_labels = labels[:-1] if len(labels) > 1 else labels
    name = "-".join(name_labels)

    if rules.THAI_BRAND_PATTERN.search(name):
        v.thai = True

    strong = [k for k in rules.STRONG_KEYWORDS if k in name]
    if strong:
        v.add("strong_keyword", ",".join(strong))

    has_number = bool(rules.NUMBER_PATTERN.search(name))
    weak = [k for k in rules.WEAK_KEYWORDS if k in name]
    if weak and (has_number or strong):
        v.add("weak_keyword_combo", ",".join(weak))
    if has_number and (weak or strong):
        v.add("number_pattern", rules.NUMBER_PATTERN.search(name).group(0))

    institution = is_institution(host)
    if tld in rules.CHEAP_TLDS and not institution:
        # A cheap TLD alone is weak evidence; halve it when nothing else matched.
        weight = rules.WEIGHTS["cheap_tld"] if (strong or weak) else rules.WEIGHTS["cheap_tld"] // 3
        v.add("cheap_tld", "." + tld, weight)

    if (strong or weak) and any(rules.ROTATION_PATTERN.search(lbl) for lbl in name_labels):
        v.add("rotation_suffix", name)

    if len(labels) >= 4 and not institution:
        v.add("deep_subdomain", f"{len(labels)} levels")

    path_hits = [p.pattern for p in rules.SUSPICIOUS_PATH_PATTERNS if p.search(path_q)]
    if path_hits:
        key = "suspicious_path_on_institution" if institution else "suspicious_path"
        v.add(key, path_q[:120])

    return v
