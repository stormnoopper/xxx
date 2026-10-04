import unittest
from unittest import mock

from gambling_bot import registry
from gambling_bot.classifier import Verdict


def alive(url, score=90, thai=True):
    return Verdict(url=url, score=score, status=200, thai=thai, reasons=["strong_keyword: ufabet"])


def dead(url):
    return Verdict(url=url, error="URLError: <urlopen error [Errno 8] nodename nor servname provided>")


class TestMerge(unittest.TestCase):
    def run_day(self, rows, day, verdicts, close_after=2):
        with mock.patch.object(registry, "today", return_value=day):
            return registry.merge(rows, verdicts, close_after)

    def test_lifecycle_new_active_closed_reopened(self):
        rows = {}
        s = self.run_day(rows, "2026-10-04", [alive("https://ufabet168.xyz")])
        self.assertEqual(s["new"], 1)
        row = rows["ufabet168.xyz"]
        self.assertEqual((row["status"], row["first_seen"], row["last_seen"]), ("active", "2026-10-04", "2026-10-04"))

        # first miss: still active (could be a network blip)
        s = self.run_day(rows, "2026-10-05", [dead("https://ufabet168.xyz")])
        self.assertEqual((row["status"], row["fail_count"], s["failing"]), ("active", "1", 1))

        # second consecutive miss: closed
        s = self.run_day(rows, "2026-10-06", [dead("https://ufabet168.xyz")])
        self.assertEqual((row["status"], row["closed_at"], s["closed_today"]), ("closed", "2026-10-06", 1))
        self.assertEqual(row["last_seen"], "2026-10-04")
        self.assertEqual(row["close_reason"], "URLError")

        s = self.run_day(rows, "2026-10-07", [dead("https://ufabet168.xyz")])
        self.assertEqual(s["still_closed"], 1)

        # comes back
        s = self.run_day(rows, "2026-10-08", [alive("https://www.ufabet168.xyz")])
        self.assertEqual((row["status"], row["reopened_at"], row["closed_at"], s["reopened"]),
                         ("active", "2026-10-08", "", 1))

    def test_blip_resets_fail_count(self):
        rows = {}
        self.run_day(rows, "d1", [alive("https://a-slot.xyz")])
        self.run_day(rows, "d2", [dead("https://a-slot.xyz")])
        self.run_day(rows, "d3", [alive("https://a-slot.xyz")])
        self.run_day(rows, "d4", [dead("https://a-slot.xyz")])
        self.assertEqual(rows["a-slot.xyz"]["status"], "active")

    def test_parked_domain_counts_as_gone(self):
        rows = {}
        self.run_day(rows, "d1", [alive("https://a-slot.xyz")], close_after=1)
        self.run_day(rows, "d2", [Verdict(url="https://a-slot.xyz", score=5, status=200)], close_after=1)
        self.assertEqual(rows["a-slot.xyz"]["status"], "closed")
        self.assertIn("no gambling content", rows["a-slot.xyz"]["close_reason"])

    def test_new_sites_must_be_reachable_and_thai(self):
        rows = {}
        s = self.run_day(rows, "d1", [dead("https://x-slot.xyz"), alive("https://casino-es.top", thai=False)])
        self.assertEqual((s["new"], rows), (0, {}))


if __name__ == "__main__":
    unittest.main()
