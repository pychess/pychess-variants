"""Direct blog cover images follow the same allowlist as Markdown images."""

import unittest

from ublog import image_src, sanitize_image_url


class BlogCoverImageTests(unittest.TestCase):
    def test_approved_external_hosts_load_directly(self):
        for url in (
            "https://i.imgur.com/example.jpg",
            "https://upload.wikimedia.org/wikipedia/commons/example.svg",
            "https://image.lichess1.org/a.png",
        ):
            with self.subTest(url=url):
                self.assertEqual(image_src({"_id": "abcd1234", "image": url}), url)

    def test_local_and_versioned_cdn_images(self):
        self.assertEqual(image_src({"image": "/images/a.svg"}), "/static/images/a.svg")
        self.assertEqual(image_src({"image": "/icons/a.svg"}), "/static/icons/a.svg")
        self.assertEqual(image_src({"image": "/static/docs/a.svg"}), "/static/docs/a.svg")
        cdn = "https://cdn.jsdelivr.net/gh/pychess/pychess-variants@1.11.78/static/images/a.svg"
        self.assertEqual(image_src({"image": cdn}), cdn)

    def test_missing_cover_uses_template_fallback(self):
        from pathlib import Path

        templates = Path(__file__).resolve().parents[1] / "templates"
        for name in (
            "ublog_index.html",
            "ublog_community.html",
            "ublog_post.html",
            "profile.html",
            "blogs.html",
        ):
            with self.subTest(template=name):
                self.assertIn("ublog-default-cover.svg", (templates / name).read_text())
        self.assertEqual(image_src({"image": ""}), "")
        self.assertEqual(image_src({"image": "https://untrusted.example/a.png"}), "")

    def test_unapproved_urls_never_become_cover_sources(self):
        for url in (
            "https://bad.example/image.png",
            "https://imgur.com.evil.example/image.png",
            "https://cdn.jsdelivr.net/gh/attacker/repo@1/static/images/a.svg",
            "http://i.imgur.com/image.png",
            "//evil.example/image.svg",
            "javascript:alert(1)",
            "/blogs/image/abcd1234",
            "https://i.imgur.com:1234/a.png",
            "https://i.imgur.com:invalid/a.png",
        ):
            with self.subTest(url=url):
                self.assertIsNone(sanitize_image_url(url))
                self.assertEqual(image_src({"_id": "abcd1234", "image": url}), "")
