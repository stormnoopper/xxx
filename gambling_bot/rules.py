"""Heuristic rules for spotting gambling URLs. Tune weights/lists here only."""

import re

# Strong keywords: substring match in hostname is enough.
STRONG_KEYWORDS = [
    "casino", "slot", "baccarat", "bacara", "ufabet", "sbobet", "betflik",
    "lotto", "huay", "jackpot", "roulette", "pgslot", "joker", "sagame",
    "sexybaccarat", "betway", "poker", "spin", "gclub", "lsm99", "auto-bet",
]

# Weak keywords: count only when paired with a number pattern or strong keyword
# (avoids false positives like "alphabet", "pgadmin", "vipshop").
WEAK_KEYWORDS = ["bet", "ufa", "pg", "vip", "win", "lucky", "mega", "royal"]

# Number patterns commonly appended to gambling brands.
NUMBER_PATTERN = re.compile(r"(168|789|888|999|777|666|365|24|99|88|69|911)")

CHEAP_TLDS = {
    "xyz", "club", "vip", "top", "online", "site", "icu", "fun", "win", "bet",
    "casino", "games", "live", "life", "shop", "store", "cc", "me", "io",
    "asia", "pro", "info", "biz", "link", "click", "work", "bond", "cfd", "sbs",
}

# Domain rotation markers: brand-2, brand-th, brand-net, brand2025 ...
ROTATION_PATTERN = re.compile(r"(-\d{1,3}|-th|-net|-new|-auto|-vip|\d{3,4})$")

URL_SHORTENERS = {
    "bit.ly", "cutt.ly", "tinyurl.com", "t.co", "goo.gl", "is.gd", "ow.ly",
    "rebrand.ly", "shorturl.at", "s.id", "rb.gy", "t.ly", "tiny.cc", "lin.ee",
}

# Legit institutional suffixes that are often hacked and injected with gambling pages.
INSTITUTION_SUFFIXES = (
    ".go.th", ".ac.th", ".or.th", ".in.th", ".mi.th", ".gov", ".edu",
    ".ac.id", ".go.id", ".edu.vn", ".gov.ph",
)

# Paths typical of injected spam pages on compromised sites.
SUSPICIOUS_PATH_PATTERNS = [
    re.compile(r"/(slot|slots|casino|baccarat|ufa|ufabet|pg|bet|huay|lotto)[/\-_.]", re.I),
    re.compile(r"[?&]p=\d{3,}", re.I),
    re.compile(r"[?&](slot|bet|casino|game)=", re.I),
    re.compile(r"/wp-content/uploads/.+\.html?$", re.I),
]

# Page-content keywords (Thai + English). Matched case-insensitively.
CONTENT_KEYWORDS = [
    "สล็อต", "บาคาร่า", "คาสิโน", "แทงบอล", "หวยออนไลน์", "เครดิตฟรี",
    "ฝากถอน", "ฝาก-ถอน", "เว็บตรง", "ไม่ผ่านเอเย่นต์", "ไม่มีขั้นต่ำ", "แตกง่าย",
    "สมัครสมาชิก", "ทดลองเล่น", "โปรโมชั่น", "ยูฟ่า", "พนันออนไลน์", "แจกเครดิต",
    "slot online", "pg slot", "ufabet", "baccarat", "casino online", "free credit",
    "sbobet", "jackpot", "wallet", "true wallet",
]

# Inline styles used to hide injected links.
HIDDEN_STYLE_PATTERN = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0"
    r"|left\s*:\s*-\d{3,}px|top\s*:\s*-\d{3,}px|opacity\s*:\s*0(\.0+)?\s*(;|$)"
    r"|height\s*:\s*0(px)?\s*;.*overflow\s*:\s*hidden|text-indent\s*:\s*-\d{3,}",
    re.I,
)

WEIGHTS = {
    "strong_keyword": 35,
    "weak_keyword_combo": 20,
    "number_pattern": 10,
    "cheap_tld": 15,
    "rotation_suffix": 10,
    "deep_subdomain": 10,
    "shortener": 5,
    "suspicious_path_on_institution": 30,
    "suspicious_path": 10,
    "content_keyword": 5,      # per distinct keyword hit
    "content_keyword_cap": 40,
    "hidden_gambling_link": 40,
}

THRESHOLD_SUSPECT = 30
THRESHOLD_GAMBLING = 60

THAI_CHARS = re.compile(r"[\u0E00-\u0E7F]")

# Brands/terms specific to the Thai gambling market (used to keep blocklist candidates
# and to tag results as Thai even when the page content cannot be read).
THAI_BRAND_PATTERN = re.compile(
    r"ufabet|ufa\d|ufa-|betflik|pgslot|pg-slot|slotxo|superslot|sagame|lsm99|gclub|ambbet"
    r"|biobet|lucabet|mafia88|joker123|jokergaming|ufac4|huaythai|ruay|lottovip|thai|(?:^|[.-])th(?:[.-]|$)",
    re.I,
)

CHALLENGE_PATTERN = re.compile(r"Just a moment\.\.\.|cf-browser-verification|challenge-platform", re.I)

# Discovery: search queries (Thai market) run against Bing.
SEARCH_QUERIES = [
    "สล็อต เว็บตรง", "สล็อต pg เว็บตรง แตกง่าย", "บาคาร่า ออนไลน์", "ufabet ทางเข้า",
    "แทงบอลออนไลน์ เว็บตรง", "หวยออนไลน์ เว็บไหนดี", "เครดิตฟรี กดรับเอง", "betflik ทางเข้า",
    "สล็อต ฝากถอน true wallet", "เว็บพนันออนไลน์ ไม่ผ่านเอเย่นต์", "คาสิโนออนไลน์ เว็บตรง",
    "pg slot ทดลองเล่น", "สมัคร ufa168", "sagame บาคาร่า", "superslot เครดิตฟรี",
    # compromised institution sites
    "สล็อต ac.th", "สล็อต go.th", "บาคาร่า ac.th", "slot เว็บตรง site:ac.th", "ufabet site:go.th",
]

# Public gambling blocklists (domains), filtered with THAI_BRAND_PATTERN.
BLOCKLISTS = [
    "https://blocklistproject.github.io/Lists/alt-version/gambling-nl.txt",
    "https://raw.githubusercontent.com/hagezi/dns-blocklists/main/wildcard/gambling-onlydomains.txt",
]

# Certificate Transparency keywords (crt.sh, often slow/unavailable).
CT_KEYWORDS = ["ufabet", "betflik", "pgslot", "superslot", "slotxo", "sagame"]

# Hosts that show up in search results but are not gambling operators.
IGNORE_HOSTS = (
    "facebook.com", "youtube.com", "wikipedia.org", "wiktionary.org", "bing.com", "microsoft.com",
    "google.com", "tiktok.com", "x.com", "twitter.com", "instagram.com", "pantip.com",
    "longdo.com", "line.me", "apple.com", "play.google.com", "reddit.com", "linkedin.com",
)
