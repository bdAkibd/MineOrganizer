import unittest
from services.manual import load_manual_html, manual_path


class TestManual(unittest.TestCase):
    def test_manual_is_available_in_english(self):
        manual = load_manual_html()

        self.assertIn("MineOrganizer User Manual", manual)
        self.assertIn("Game environments", manual)
        self.assertIn("Resource packs and shaders", manual)
        self.assertIn('<html lang="en">', manual)

    def test_localized_manuals_are_available_for_supported_locales(self):
        for locale in ("ru", "de", "es", "fr", "uk", "it", "zh_CN", "zh_TW", "ja", "pt"):
            manual = load_manual_html(locale)
            self.assertTrue(manual_path(locale).is_file())
            self.assertIn("<html", manual)
            self.assertIn("<h1>", manual)

    def test_russian_manual_is_selected_for_russian_locale(self):
        manual = load_manual_html("ru")

        self.assertEqual(manual_path("ru").name, "manual_ru.html")
        self.assertIn('<html lang="ru">', manual)

    def test_missing_manual_locale_falls_back_to_english(self):
        self.assertEqual(load_manual_html("missing"), load_manual_html("en"))

