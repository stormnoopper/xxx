# gambling_bot

Bot ตรวจจับ URL / เว็บพนันออนไลน์ และลิงก์พนันที่ถูกฝังในเว็บที่ถูกแฮก (Python stdlib, ไม่ต้องลง dependency; มี `certifi` จะใช้ CA bundle นั้นให้อัตโนมัติ)

## Commands

```bash
# 0) หา candidate URL เอง: Bing (คำค้นไทย 20 ชุด) + public gambling blocklist (กรองแบรนด์ไทย)
python3 -m gambling_bot discover -o data/candidates.txt            # --sources search,blocklist,ct
python3 -m gambling_bot scan data/candidates.txt --workers 32 --insecure --expand 1 \
    --thai-only --alive-only -o data/results.csv

# 1) ตรวจจากรูปแบบ URL อย่างเดียว (offline)
python3 -m gambling_bot classify urls.example.txt -o result.csv

# 2) Fetch จริง: ตาม redirect / ลิงก์สั้น, วิเคราะห์เนื้อหา + hidden link
python3 -m gambling_bot scan urls.example.txt -o result.json --delay 1

# 3) Crawl เว็บหน่วยงาน/โรงเรียน หา page /slot/, ?p=xxxx และลิงก์พนันที่ซ่อนไว้
python3 -m gambling_bot crawl https://www.example.ac.th --max-pages 100 -o audit.csv
```

Scan options: `--workers` (parallel, default 16), `--expand N` (ตามลิงก์จากเว็บพนันไปหาเว็บเครือเดียวกัน N รอบ), `--thai-only`, `--alive-only`

Options: `--all` (แสดง CLEAN ด้วย), `--timeout`, `--delay` (วินาทีต่อ request), `--insecure` (ข้าม TLS verify — เว็บพนันมัก cert เสีย)

## Rules → signal

| ลักษณะ | Signal | Weight |
|---|---|---|
| คำพนันในโดเมน (casino, slot, ufabet, huay …) | `strong_keyword` | 35 |
| bet / ufa / pg / vip + ตัวเลข 168, 789, 888 … | `weak_keyword_combo`, `number_pattern` | 20 + 10 |
| TLD ราคาถูก (.xyz .club .vip .top .online .site .icu …) | `cheap_tld` | 15 (5 ถ้าไม่มี keyword) |
| เปลี่ยนโดเมนบ่อย (-2, -th, -net, เลขท้าย) | `rotation_suffix` | 10 |
| subdomain ≥ 4 ชั้น | `deep_subdomain` | 10 |
| ลิงก์สั้น (bit.ly, cutt.ly …) → resolve แล้วให้คะแนนปลายทาง | `shortener` | 5 |
| `/slot/`, `?p=xxxx` บนโดเมน .go.th / .ac.th / .or.th | `suspicious_path_on_institution` | 30 |
| คำในเนื้อหา (สล็อต, บาคาร่า, เว็บตรง, เครดิตฟรี …) | `content_keyword` | 5/คำ, cap 40 |
| `<a>` พนันใน element ที่ซ่อน (display:none, left:-9999px, font-size:0 …) | `hidden_gambling_link` | 40 |

Label: `GAMBLING` ≥ 60, `SUSPECT` ≥ 30, else `CLEAN` — ปรับ keyword/weight/threshold ได้ที่ `gambling_bot/rules.py` ไฟล์เดียว

## Test

```bash
python3 -m unittest -v
```

## Automation (GitHub Actions)

`.github/workflows/daily.yml` **รันด้วยมือ**: แท็บ Actions → *Scan & deploy* → `Run workflow` (ติ๊ก `discover` ออกถ้าจะตรวจแค่เว็บเดิม)

1. **scan** — `python -m gambling_bot update`
   - ตรวจซ้ำทุกเว็บใน `data/sites.csv` + ค้นหาเว็บใหม่ (Bing + blocklist) + ตามลิงก์ 1 รอบ
   - เปิดได้และยังเป็นเว็บพนัน → `active`, อัปเดต `last_seen`
   - ตรวจไม่พบ (เปิดไม่ได้ / HTTP 404·410·451·5xx / ไม่มีเนื้อหาพนันแล้ว) **ติดกัน 2 รอบ** → `closed` (`--close-after` ปรับได้)
   - เว็บที่ปิดแล้วกลับมาเปิด → `active` อีกครั้ง + `reopened_at`
   - commit `data/sites.csv` + `data/summary.json` กลับเข้า repo
2. **build** — Next.js static export (`web/out`)
3. **deploy** — GitHub Pages

Push ที่แก้ `web/**` จะ build + deploy อย่างเดียว ไม่ scan

### ตั้งค่าครั้งแรก
- Settings → Pages → Source: **GitHub Actions**
- Settings → Actions → General → Workflow permissions: **Read and write**

### Registry (`data/sites.csv`)
| column | ความหมาย |
|---|---|
| `status` | `active` / `closed` |
| `first_seen` / `last_seen` | วันที่พบครั้งแรก / วันล่าสุดที่ยังเปิดอยู่ |
| `closed_at` / `reopened_at` | วันที่ถูกตัดสินว่าปิด / กลับมาเปิด |
| `fail_count` / `close_reason` | จำนวนครั้งที่ตรวจไม่พบติดกัน / สาเหตุล่าสุด |

## Web (Next.js landing page)

อ่าน `data/sites.csv` + `data/summary.json` ตอน build แล้วแสดงเป็นหน้า static — โดเมนทั้งหมดแสดงแบบ defang (`ufabet168[.]xyz`) ไม่มีลิงก์ให้กด และตั้ง `noindex`

```bash
cd web
pnpm dev            # dev
pnpm refresh        # update registry + build (~40-60 นาที)
pnpm build          # static export -> web/out
```

ใช้ข้อมูลจากโฟลเดอร์อื่นได้ด้วย `DATA_DIR=/path/to/data`
