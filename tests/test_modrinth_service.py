"""Unit tests for Modrinth API service integration."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from services.modrinth_service import (
    ModrinthSearchResult,
    ModrinthVersion,
    check_mod_updates,
    download_file,
    get_project_versions,
    search_modrinth,
)


class ModrinthServiceTests(unittest.TestCase):
    @patch("services.modrinth_service._api_get")
    def test_search_modrinth_parses_results(self, mock_get):
        mock_get.return_value = {
            "hits": [
                {
                    "project_id": "AANobbMI",
                    "slug": "sodium",
                    "title": "Sodium",
                    "description": "Modern rendering engine",
                    "author": "jellysquid3",
                    "icon_url": "https://cdn.modrinth.com/icon.png",
                    "downloads": 1000000,
                    "follows": 50000,
                    "versions": ["1.20.1", "1.20.2"],
                    "categories": ["fabric", "quilt"],
                }
            ]
        }
        results = search_modrinth("sodium", loader="fabric", minecraft_version="1.20.1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].title, "Sodium")
        self.assertEqual(results[0].slug, "sodium")
        self.assertEqual(results[0].author, "jellysquid3")
        self.assertEqual(results[0].loaders, ["fabric", "quilt"])

    @patch("services.modrinth_service._api_get")
    def test_get_project_versions_parses_files_and_deps(self, mock_get):
        mock_get.return_value = [
            {
                "id": "v123",
                "project_id": "AANobbMI",
                "name": "Sodium 0.5.8",
                "version_number": "0.5.8",
                "game_versions": ["1.20.1"],
                "loaders": ["fabric"],
                "changelog": "Bug fixes",
                "files": [
                    {
                        "url": "https://cdn.modrinth.com/data/sodium.jar",
                        "filename": "sodium-0.5.8.jar",
                        "primary": True,
                        "size": 1024,
                        "hashes": {"sha1": "abc123sha1", "sha512": "abc512"},
                    }
                ],
                "dependencies": [
                    {
                        "project_id": "P7dR8mSH",
                        "version_id": None,
                        "dependency_type": "required",
                    }
                ],
            }
        ]
        versions = get_project_versions("sodium", loader="fabric", minecraft_version="1.20.1")
        self.assertEqual(len(versions), 1)
        self.assertEqual(versions[0].version_number, "0.5.8")
        self.assertEqual(len(versions[0].files), 1)
        self.assertEqual(versions[0].files[0].filename, "sodium-0.5.8.jar")
        self.assertEqual(len(versions[0].dependencies), 1)
        self.assertEqual(versions[0].dependencies[0].project_id, "P7dR8mSH")

    @patch("services.modrinth_service._api_post")
    def test_check_mod_updates(self, mock_post):
        mock_post.return_value = {
            "old_sha1": {
                "id": "new_ver_id",
                "project_id": "proj1",
                "version_number": "1.1.0",
                "files": [
                    {
                        "url": "https://cdn.modrinth.com/mod-1.1.0.jar",
                        "filename": "mod-1.1.0.jar",
                        "primary": True,
                        "size": 2048,
                    }
                ],
            }
        }
        updates = check_mod_updates(["old_sha1"], game_versions=["1.20.1"], loaders=["fabric"])
        self.assertIn("old_sha1", updates)
        self.assertEqual(updates["old_sha1"]["version_number"], "1.1.0")

    def test_download_file_creates_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            dest = Path(temp_dir) / "test_download.jar"
            mock_response = MagicMock()
            mock_response.read.side_effect = [b"mock chunk 1", b"mock chunk 2", b""]
            mock_response.headers.get.return_value = "24"
            mock_response.__enter__.return_value = mock_response

            with patch("urllib.request.urlopen", return_value=mock_response):
                download_file("https://example.com/mod.jar", dest)

            self.assertTrue(dest.exists())
            self.assertEqual(dest.read_bytes(), b"mock chunk 1mock chunk 2")


if __name__ == "__main__":
    unittest.main()
