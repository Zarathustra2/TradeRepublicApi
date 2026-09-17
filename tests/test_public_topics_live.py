"""Smoke tests against the real Trade Republic API.

These only use topics that need no account, so they are safe to run, but they
depend on the network and on Trade Republic not changing anything. They are
skipped unless you opt in::

    TRAPI_LIVE_TESTS=1 python -m unittest discover -s tests
"""

import os
import unittest

from trapi.api import TrBlockingApi

ISIN = "US0378331005"  # Apple Inc.
ETF = "IE00B4L5Y983"  # iShares Core MSCI World
CRYPTO = "XF000BTC0017"  # Bitcoin

live = unittest.skipUnless(
    os.environ.get("TRAPI_LIVE_TESTS") == "1",
    "set TRAPI_LIVE_TESTS=1 to run tests that talk to the real API",
)


@live
class PublicTopicsTest(unittest.TestCase):
    """No login happens here - these topics are served without a token."""

    @classmethod
    def setUpClass(cls):
        cls.tr = TrBlockingApi("+490000000000", "0000", timeout=20)

    def test_instrument(self):
        self.assertTrue(self.tr.instrument(ISIN)["exchangeIds"])

    def test_stock_details(self):
        self.assertEqual(self.tr.stock_details(ISIN)["isin"], ISIN)

    def test_stock_detail_kpis(self):
        self.assertIn("revenues", self.tr.stock_detail_kpis(ISIN))

    def test_stock_detail_dividends(self):
        self.assertIn("data", self.tr.stock_detail_dividends(ISIN))

    def test_ticker(self):
        self.assertIn("price", self.tr.ticker(ISIN)["bid"])

    def test_aggregate_history_light(self):
        self.assertTrue(self.tr.aggregate_history_light(ISIN, range="1d")["aggregates"])

    def test_neon_search(self):
        self.assertTrue(self.tr.neon_search(query="apple", page_size=2)["results"])

    def test_neon_news(self):
        self.assertIsInstance(self.tr.neon_news(ISIN), list)

    def test_performance(self):
        self.assertIn("price_1y", self.tr.performance(ISIN))

    def test_etf_details(self):
        self.assertEqual(self.tr.etf_details(ETF)["isin"], ETF)

    def test_etf_composition(self):
        self.assertTrue(self.tr.etf_composition(ETF)["data"])

    def test_crypto_details(self):
        self.assertEqual(self.tr.crypto_details(CRYPTO)["isin"], CRYPTO)


if __name__ == "__main__":
    unittest.main()
