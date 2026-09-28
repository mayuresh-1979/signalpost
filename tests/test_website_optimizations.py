import unittest
from unittest.mock import patch, MagicMock
from norway_company_agent.website import (
    _robots_allowed,
    _robots_cache,
    clear_robots_cache,
)


class WebsiteRobotsOptimizationTests(unittest.TestCase):
    def setUp(self):
        clear_robots_cache()

    def tearDown(self):
        clear_robots_cache()

    def test_robots_allowed_caches_origin_decision(self):
        url1 = "https://example.com/about"
        url2 = "https://example.com/contact"

        mock_response = MagicMock()
        mock_response.read.return_value = b"User-agent: *\nDisallow: /private\n"
        mock_response.__enter__.return_value = mock_response

        with patch("norway_company_agent.website.SAFE_OPENER.open", return_value=mock_response) as mock_open:
            # First call -> cache miss
            allowed1, from_cache1 = _robots_allowed(url1, 5.0, return_cached_flag=True)
            self.assertTrue(allowed1)
            self.assertFalse(from_cache1)
            self.assertEqual(mock_open.call_count, 1)

            # Second call on same origin -> cache hit!
            allowed2, from_cache2 = _robots_allowed(url2, 5.0, return_cached_flag=True)
            self.assertTrue(allowed2)
            self.assertTrue(from_cache2)
            # mock_open was NOT called again!
            self.assertEqual(mock_open.call_count, 1)

            # Disallowed path on same origin
            disallowed, from_cache_dis = _robots_allowed("https://example.com/private", 5.0, return_cached_flag=True)
            self.assertFalse(disallowed)
            self.assertTrue(from_cache_dis)
            self.assertEqual(mock_open.call_count, 1)

    def test_robots_allowed_caches_failure_gracefully(self):
        url = "https://example.org/"
        with patch("norway_company_agent.website.SAFE_OPENER.open", side_effect=Exception("Connection refused")) as mock_open:
            # First call -> fails, defaults to allowed, cached=False
            allowed1, from_cache1 = _robots_allowed(url, 5.0, return_cached_flag=True)
            self.assertTrue(allowed1)
            self.assertFalse(from_cache1)
            self.assertEqual(mock_open.call_count, 1)

            # Second call on same origin -> cache hit on failure, defaults to allowed, cached=True
            allowed2, from_cache2 = _robots_allowed("https://example.org/about", 5.0, return_cached_flag=True)
            self.assertTrue(allowed2)
            self.assertTrue(from_cache2)
            self.assertEqual(mock_open.call_count, 1)

    def test_clear_robots_cache(self):
        _robots_cache["https://test.com"] = None
        clear_robots_cache()
        self.assertEqual(len(_robots_cache), 0)

    def test_priority_links_deduplication_and_homepage_skipping(self):
        from bs4 import BeautifulSoup
        from norway_company_agent.website import _priority_links

        html = """
        <a href="/about">About</a>
        <a href="/about/">About trailing</a>
        <a href="https://www.example.com/">Homepage www</a>
        <a href="https://example.com/">Homepage apex</a>
        <a href="/kontakt">Contact</a>
        """
        soup = BeautifulSoup(html, "html.parser")
        links = _priority_links("https://example.com/", soup, limit=4)
        self.assertEqual(links, ["https://example.com/about", "https://example.com/kontakt"])

