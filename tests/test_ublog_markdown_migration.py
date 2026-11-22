import unittest

from ublog_markdown_migration import convert_legacy_blog_markdown


class TestLegacyBlogMarkdown(unittest.TestCase):
    def test_image_dimensions(self):
        self.assertEqual(
            convert_legacy_blog_markdown('<img src="/static/a.png" width="336" height="336">'),
            "![](/static/a.png){width=336 height=336}\n",
        )

    def test_unsafe_dimensions_not_copied(self):
        result = convert_legacy_blog_markdown(
            '<img src="https://evil.test/a.svg" width="999999" onerror="alert(1)">'
        )
        self.assertEqual(result, "![](https://evil.test/a.svg)\n")

    def test_convert_youtube_study_and_layout(self):
        old = '<p align="center"><iframe src="https://www.youtube.com/embed/dQw4w9WgXcQ"></iframe></p><iframe src="https://lichess.org/study/embed/abcdefgh"></iframe>'
        result = convert_legacy_blog_markdown(old)
        self.assertIn("https://www.youtube.com/watch?v=dQw4w9WgXcQ", result)
        self.assertIn("https://lichess.org/study/abcdefgh", result)
        self.assertNotIn("<iframe", result)

    def test_keeps_unknown_html_for_strict_renderer_to_escape(self):
        self.assertIn("<script>", convert_legacy_blog_markdown("<script>alert(1)</script>"))

    def test_link(self):
        self.assertEqual(
            convert_legacy_blog_markdown('<a href="https://lichess.org">Lichess</a>'),
            "[Lichess](https://lichess.org)\n",
        )
