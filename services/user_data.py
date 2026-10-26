"""Store user tags and profiles outside game directories."""

import json
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

from models.profile import Profile


def default_user_data_path() -> Path:
    """Return the MineOrganizer user data path."""
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "MineOrganizer" / "user_data.json"
    return Path.home() / ".local" / "share" / "MineOrganizer" / "user_data.json"


class UserDataStore:
    """Read and safely save tags and profile descriptions as JSON."""

    def __init__(self, path: Path | None = None) -> None:
        """Load user data from the specified or default file."""
        self.path = path or default_user_data_path()
        self.data: dict[str, Any] = {
            "version": 1,
            "mod_tags": {},
            "minecraft_version_overrides": {},
            "profiles": [],
            "game_dirs": [],
        }
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                tags = loaded.get("mod_tags", {})
                profiles = loaded.get("profiles", [])
                self.data["mod_tags"] = tags if isinstance(tags, dict) else {}
                overrides = loaded.get("minecraft_version_overrides", {})
                self.data["minecraft_version_overrides"] = overrides if isinstance(overrides, dict) else {}
                self.data["profiles"] = profiles if isinstance(profiles, list) else []
                game_dirs = loaded.get("game_dirs", [])
                self.data["game_dirs"] = game_dirs if isinstance(game_dirs, list) else []
                for profile in self.data["profiles"]:
                    if isinstance(profile, dict):
                        profile.setdefault("enabled_resourcepack_hashes", [])
                        profile.setdefault("enabled_shaderpack_hashes", [])
        except (OSError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        """Atomically save JSON without touching game files."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", encoding="utf-8", dir=self.path.parent, delete=False, suffix=".tmp"
            ) as temporary_file:
                json.dump(self.data, temporary_file, ensure_ascii=False, indent=2)
                temporary_path = Path(temporary_file.name)
            temporary_path.replace(self.path)
        finally:
            if temporary_path is not None and temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

    def tags_for(self, sha256: str) -> list[str]:
        """Return tags for a file by its hash."""
        value = self.data["mod_tags"].get(sha256, [])
        return [str(tag) for tag in value if isinstance(tag, str)] if isinstance(value, list) else []

    def set_tags(self, sha256: str, tags: list[str]) -> None:
        """Save unique file tags by SHA-256."""
        normalized = list(dict.fromkeys(tag.strip() for tag in tags if tag.strip()))
        if normalized:
            self.data["mod_tags"][sha256] = normalized
        else:
            self.data["mod_tags"].pop(sha256, None)
        self.save()

    def minecraft_versions_for(self, sha256: str) -> list[str]:
        """Return a user's Minecraft-version override for a mod file."""
        value = self.data["minecraft_version_overrides"].get(sha256, [])
        return [str(version) for version in value if isinstance(version, str)] if isinstance(value, list) else []

    def set_minecraft_versions(self, sha256: str, versions: list[str]) -> None:
        """Persist or clear a user's Minecraft-version override for a mod."""
        normalized = list(dict.fromkeys(version.strip() for version in versions if version.strip()))
        if normalized:
            self.data["minecraft_version_overrides"][sha256] = normalized
        else:
            self.data["minecraft_version_overrides"].pop(sha256, None)
        self.save()

    def profiles(self) -> list[dict[str, Any]]:
        """Return the profile list."""
        return self.data["profiles"]

    def get_profile(self, profile_id: str) -> Profile | None:
        """Find a profile by ID and return it as a Profile domain model instance."""
        for p in self.data["profiles"]:
            if isinstance(p, dict) and p.get("id") == profile_id:
                return Profile.from_dict(p)
        return None

    def get_profile_models(self) -> list[Profile]:
        """Return all profiles as Profile domain model instances."""
        return [Profile.from_dict(p) for p in self.data["profiles"] if isinstance(p, dict)]

    def add_profile(self, name: str, instance: dict[str, str], mod_hashes: list[str]) -> dict[str, Any]:
        """Create a profile linked to a Prism instance and mod set."""
        profile = {
            "id": uuid.uuid4().hex,
            "name": name.strip(),
            "instance_id": instance["instance_id"],
            "instance_path": instance["instance_path"],
            "minecraft_version": instance["minecraft_version"],
            "loader": instance["loader"],
            "loader_version": instance["loader_version"],
            "enabled_mod_hashes": list(dict.fromkeys(mod_hashes)),
            "enabled_resourcepack_hashes": [],
            "enabled_shaderpack_hashes": [],
        }
        self.data["profiles"].append(profile)
        self.save()
        return profile

    def update_profile_mods(self, profile_id: str, mod_hashes: list[str]) -> bool:
        """Update the saved mod set for a profile."""
        for profile in self.data["profiles"]:
            if profile.get("id") == profile_id:
                profile["enabled_mod_hashes"] = list(dict.fromkeys(mod_hashes))
                self.save()
                return True
        return False


    def update_profile_assets(self, profile_id: str, kind: str, asset_hashes: list[str]) -> bool:
        """Updates resource pack or shader pack selection for a profile."""
        field = "enabled_resourcepack_hashes" if kind == "resourcepacks" else "enabled_shaderpack_hashes"
        for profile in self.data["profiles"]:
            if profile.get("id") == profile_id:
                profile[field] = list(dict.fromkeys(asset_hashes))
                self.save()
                return True
        return False

    def rename_profile(self, profile_id: str, name: str) -> bool:
        """Rename a profile."""
        for profile in self.data["profiles"]:
            if profile.get("id") == profile_id:
                profile["name"] = name.strip()
                self.save()
                return True
        return False

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile record without deleting game files."""
        before = len(self.data["profiles"])
        self.data["profiles"] = [profile for profile in self.data["profiles"] if profile.get("id") != profile_id]
        if len(self.data["profiles"]) != before:
            self.save()
            return True
        return False
