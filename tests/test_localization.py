"""Tests for the localization layer."""

import unittest
import re

from services.localization import (
    LOCALE_NAMES,
    SUPPORTED_LOCALES,
    TRANSLATIONS,
    locale_name,
    translate,
    translate_many,
)


class LocalizationTests(unittest.TestCase):
    def test_english_translation_and_russian_source(self) -> None:
        self.assertEqual(translate("Settings", "en"), "Settings")
        self.assertEqual(translate("Settings", "ru"), "Настройки")
        self.assertEqual(
            translate("Environment check completed: 3 records, external mods not imported: 1", "en"),
            "Environment check completed: 3 records, external mods not imported: 1",
        )
        self.assertEqual(translate("Source", "en"), "Source")
        self.assertEqual(translate("The config folder was not found in the instance.", "en"), "The config folder was not found in the instance.")
        self.assertEqual(translate("Resource packs", "en"), "Resource packs")
        self.assertEqual(translate("Copy of library file", "en"), "Copy of library file")
        self.assertEqual(
            translate("Create a profile to manage resource packs and shaders.", "en"),
            "Create a profile to manage resource packs and shaders.",
        )
        self.assertEqual(
            translate('Profile "Test" created. Game files were not changed.', "en"),
            'Profile "Test" created. Game files were not changed.',
        )

    def test_translate_many_preserves_order(self) -> None:
        self.assertEqual(
            translate_many(["Source", "Size", "Path"], "en"),
            ["Source", "Size", "Path"],
        )

    def test_switching_from_english_to_additional_locale(self) -> None:
        self.assertEqual(translate("Ready", "de"), "Fertig")
        self.assertEqual(translate("Fertig", "en"), "Ready")
        self.assertEqual(translate("Ready", "ru"), "Готово")
        self.assertEqual(translate("Fertig", "ru"), "Готово")
        self.assertEqual(
            translate("Metadata read from environment JSON", "ru"),
            "Метаданные прочитаны из JSON окружения",
        )
        self.assertEqual(
            translate("Metadata read from environments JSON", "ru"),
            "Метаданные прочитаны из JSON окружения",
        )
        self.assertEqual(
            translate("Metadata read from environment JSON", "de"),
            "Metadaten aus Umgebungs-JSON gelesen",
        )

    def test_table_header_translation_does_not_repeat_source_text(self) -> None:
        for locale in SUPPORTED_LOCALES:
            self.assertNotIn("NameName", translate("Name", locale))
            self.assertNotIn("Name", translate("Name", locale)[len("Name"):])

    def test_supported_locales_are_stable(self) -> None:
        self.assertIn("en", SUPPORTED_LOCALES)
        self.assertIn("ru", SUPPORTED_LOCALES)
        self.assertEqual(len(SUPPORTED_LOCALES), len(set(SUPPORTED_LOCALES)))
        self.assertTrue(all(locale_name(locale) for locale in SUPPORTED_LOCALES))

    def test_all_locales_have_full_key_parity(self) -> None:
        base_keys = set(TRANSLATIONS["ru"].keys())
        self.assertGreater(len(base_keys), 350)
        for loc in SUPPORTED_LOCALES:
            if loc == "en":
                continue
            self.assertIn(loc, TRANSLATIONS)
            loc_keys = set(TRANSLATIONS[loc].keys())
            self.assertEqual(
                loc_keys,
                base_keys,
                f"Locale {loc} is missing {base_keys - loc_keys} or has extra {loc_keys - base_keys}",
            )

    def test_parameterized_template_translation(self) -> None:
        self.assertEqual(
            translate("Game environments found: {count}", "en", count=4),
            "Game environments found: 4",
        )
        self.assertEqual(
            translate("Game environments found: {count}", "ru", count=4),
            "Найдено игровых окружений: 4",
        )
        self.assertEqual(
            translate("Game environments found: {count}", "de", count=4),
            "Spielumgebungen gefunden: 4",
        )
        self.assertEqual(
            translate("Showing: {visible} of {total} mods", "ru", visible=12, total=30),
            "Отображается: 12 из 30 модов",
        )
        self.assertEqual(
            translate("Added {count} mod(s) to profile \"{name}\".", "ru", count=2, name="Fabric"),
            'Добавлено модов в профиль «Fabric»: 2.',
        )

    def test_safe_handling_of_missing_kwargs(self) -> None:
        # If kwargs are missing, returns the unformatted template without raising
        self.assertEqual(
            translate("Target folder: {path}", "en"),
            "Target folder: {path}",
        )

    def test_collision_free_reverse_resolution(self) -> None:
        # International words that are identical in English and other languages
        self.assertEqual(translate("Status", "en"), "Status")
        self.assertEqual(translate("Status", "de"), "Status")
        self.assertEqual(translate("Status", "ru"), "Статус")

        # Historical Russian aliases resolve correctly to canonical English and other languages
        self.assertEqual(translate("Предварительный просмотр", "en"), "Preview")
        self.assertEqual(translate("Предпросмотр", "en"), "Preview")
        self.assertEqual(translate("Предварительный просмотр", "de"), "Vorschau")
        self.assertEqual(translate("Папка не распознана", "en"), "Folder not recognized")
        self.assertEqual(translate("Каталог не распознан", "en"), "Folder not recognized")

    def test_template_parameters_consistency_across_all_translations(self) -> None:
        param_pattern = re.compile(r"\{([a-zA-Z0-9_]+)\}")
        for key in TRANSLATIONS["ru"].keys():
            expected = set(param_pattern.findall(key))
            if expected:
                for loc, d in TRANSLATIONS.items():
                    actual = set(param_pattern.findall(d[key]))
                    self.assertEqual(
                        actual,
                        expected,
                        f"Mismatch in key {key!r} for locale {loc}: expected {expected}, got {actual}",
                    )
