import unittest

from gambling_bot.classifier import Verdict, score_url
from gambling_bot.fetcher import analyze_content


class TestUrlShape(unittest.TestCase):
    def assertLabel(self, url, label):
        v = score_url(url)
        self.assertEqual(v.label, label, f"{url} -> {v.score} {v.reasons}")

    def test_keyword_plus_number_and_cheap_tld(self):
        for url in ["ufabet168.xyz", "pgslot789.club", "https://casino888vip.top",
                    "betflik-2.online", "slot-th.site", "huay24.icu"]:
            self.assertLabel(url, "GAMBLING")

    def test_rotation_suffix(self):
        v = score_url("ufa789-net.com")
        self.assertTrue(any(r.startswith("rotation_suffix") for r in v.reasons), v.reasons)

    def test_deep_subdomain(self):
        v = score_url("https://a.b.slot168.xyz")
        self.assertTrue(any(r.startswith("deep_subdomain") for r in v.reasons))

    def test_shortener_flagged_but_not_judged(self):
        v = score_url("https://bit.ly/3abcDEF")
        self.assertEqual(v.label, "CLEAN")
        self.assertTrue(v.reasons[0].startswith("shortener"))

    def test_hacked_institution_path(self):
        self.assertLabel("https://www.school.ac.th/slot/pg-slot-168", "SUSPECT")
        self.assertLabel("https://agency.go.th/?p=48213", "SUSPECT")

    def test_clean_sites(self):
        for url in ["https://www.google.com", "https://alphabet.com", "https://pgadmin.org",
                    "https://www.chula.ac.th/news/?id=12", "https://github.com/topics/vip",
                    "https://example.xyz"]:
            self.assertLabel(url, "CLEAN")


class TestContent(unittest.TestCase):
    HACKED = """
    <html><body><h1>โรงเรียนตัวอย่าง</h1><p>ข่าวประชาสัมพันธ์</p>
      <div style="position:absolute; left:-9999px">
        <a href="https://ufabet168.xyz">ufabet</a>
        <span><a href="https://pgslot789.club/register">สล็อต เว็บตรง</a></span>
      </div>
      <a href="https://www.moe.go.th">กระทรวงศึกษาธิการ</a>
      <div hidden><a href="https://example.org">harmless hidden</a></div>
    </body></html>"""

    def test_hidden_gambling_links_detected(self):
        v = Verdict(url="https://school.ac.th")
        analyze_content(self.HACKED, "https://school.ac.th", v)
        self.assertEqual(v.hidden_links, ["https://ufabet168.xyz", "https://pgslot789.club/register"])
        self.assertIn(v.label, ("SUSPECT", "GAMBLING"))

    def test_gambling_landing_content(self):
        html = "<p>สล็อต เว็บตรง ไม่ผ่านเอเย่นต์ ฝากถอน ไม่มีขั้นต่ำ เครดิตฟรี บาคาร่า</p>"
        v = Verdict(url="x")
        analyze_content(html, "https://x.com", v)
        self.assertGreaterEqual(v.score, 30)


class TestRedirect(unittest.TestCase):
    def test_domain_hop_not_double_counted(self):
        from unittest import mock
        from gambling_bot import fetcher
        f = mock.Mock()
        f.get.return_value = (200, "https://www.ufabet168.xyz/", "<p>hi</p>", ["https://www.ufabet168.xyz/"])
        v, _ = fetcher.inspect("ufabet168.xyz", f)
        self.assertEqual(v.score, score_url("ufabet168.xyz").score)
        self.assertEqual(sum(r.startswith("strong_keyword") for r in v.reasons), 1)


if __name__ == "__main__":
    unittest.main()
