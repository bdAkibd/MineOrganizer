"""Unit tests for the Minecraft crash log and latest.log analyzer."""

import tempfile
import unittest
from pathlib import Path

from services.log_analyzer import (
    analyze_instance_logs,
    analyze_log_content,
    list_available_log_files,
    read_log_text_safely,
)


class LogAnalyzerTests(unittest.TestCase):
    def test_detects_out_of_memory(self):
        text = """---- Minecraft Crash Report ----
Time: 2026-10-25 12:00:00
Description: Initializing game

java.lang.OutOfMemoryError: Java heap space
\tat java.base/java.util.Arrays.copyOf(Arrays.java:3537)
"""
        analysis = analyze_log_content(text, Path("crash.txt"))
        self.assertEqual(analysis.category, "out_of_memory")
        self.assertIn("RAM", analysis.summary)
        self.assertIn("launcher settings", analysis.recommendation.lower())

    def test_detects_java_version_mismatch(self):
        text = """---- Minecraft Crash Report ----
java.lang.UnsupportedClassVersionError: net/example/mod/Main has been compiled by a more recent version of the Java Runtime (class file version 65.0), this version of the Java Runtime only recognizes class file versions up to 61.0
"""
        analysis = analyze_log_content(text, Path("crash.txt"))
        self.assertEqual(analysis.category, "java_version")
        self.assertIn("Java 21", analysis.summary)
        self.assertIn("Java 17", analysis.summary)

    def test_detects_missing_dependencies(self):
        text = """net.fabricmc.loader.impl.FormattedException: Some of your mods are incomplete and require additional mods to be installed:
 - Mod 'sodium' (0.5.8) requires 'fabric-api' (>=0.90.0)
"""
        analysis = analyze_log_content(text, Path("latest.log"), file_type="log")
        self.assertEqual(analysis.category, "missing_dependency")
        self.assertIn("fabric-api", analysis.suspected_mods)

    def test_detects_duplicate_mods(self):
        text = """Duplicate mods found with id 'jei':
 - jei-1.20.1-15.2.0.jar
 - jei-1.20.1-15.3.0.jar
"""
        analysis = analyze_log_content(text, Path("latest.log"), file_type="log")
        self.assertEqual(analysis.category, "duplicate_mod")
        self.assertIn("jei", analysis.suspected_mods)

    def test_detects_mixin_conflict_and_known_packages(self):
        text = """org.spongepowered.asm.mixin.transformer.throwables.MixinTransformerError: An unexpected critical error was encountered
Caused by: org.spongepowered.asm.mixin.injection.throwables.InjectionError: Critical injection failure
\tat net.coderbot.iris.mixin.LevelRendererMixin.injectRender(LevelRendererMixin.java:45)
"""
        analysis = analyze_log_content(text, Path("crash.txt"))
        self.assertEqual(analysis.category, "mixin_conflict")
        self.assertIn("Iris Shaders", analysis.suspected_mods)

    def test_finds_and_sorts_log_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            instance = Path(temp_dir)
            crash_dir = instance / "crash-reports"
            crash_dir.mkdir(parents=True)
            logs_dir = instance / "logs"
            logs_dir.mkdir(parents=True)

            crash1 = crash_dir / "crash-2026-10-24_10.00.00-client.txt"
            crash1.write_text("Old crash", encoding="utf-8")
            crash2 = crash_dir / "crash-2026-10-25_11.00.00-client.txt"
            crash2.write_text("java.lang.OutOfMemoryError: Java heap space", encoding="utf-8")
            latest_log = logs_dir / "latest.log"
            latest_log.write_text("[INFO] Started", encoding="utf-8")

            files = list_available_log_files(instance)
            self.assertGreaterEqual(len(files), 2)

            analysis = analyze_instance_logs(instance)
            self.assertIsNotNone(analysis)
            self.assertEqual(analysis.category, "out_of_memory")

    def test_read_log_text_safely_truncates_large_files(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "huge.log"
            # Write 500 KB log
            chunk = "Line of log output test data\n" * 100
            log_path.write_text(chunk * 100, encoding="utf-8")

            # Read with a 2 KB limit
            safe_text = read_log_text_safely(log_path, max_bytes=2048)
            self.assertIn("Large log file", safe_text)
            self.assertLessEqual(len(safe_text.encode("utf-8")), 3000)

    def test_read_log_text_safely_missing_file(self):
        missing = Path("non_existent_log_file.log")
        self.assertEqual(read_log_text_safely(missing), "")


if __name__ == "__main__":
    unittest.main()
