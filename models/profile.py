"""Domain model for a user profile."""

from dataclasses import dataclass, field
import uuid
from typing import Any


@dataclass(slots=True)
class Profile:
    """Store configuration and active asset hashes for a game profile."""

    id: str
    name: str
    instance_id: str = ""
    instance_path: str = ""
    minecraft_version: str = ""
    loader: str = ""
    loader_version: str = ""
    enabled_mod_hashes: list[str] = field(default_factory=list)
    enabled_resourcepack_hashes: list[str] = field(default_factory=list)
    enabled_shaderpack_hashes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        """Instantiate a Profile from dictionary data, supplying defaults for missing fields."""
        return cls(
            id=str(data.get("id", "") or uuid.uuid4().hex),
            name=str(data.get("name", "")).strip(),
            instance_id=str(data.get("instance_id", "")),
            instance_path=str(data.get("instance_path", "")),
            minecraft_version=str(data.get("minecraft_version", "")),
            loader=str(data.get("loader", "")),
            loader_version=str(data.get("loader_version", "")),
            enabled_mod_hashes=list(dict.fromkeys(data.get("enabled_mod_hashes", []))),
            enabled_resourcepack_hashes=list(dict.fromkeys(data.get("enabled_resourcepack_hashes", []))),
            enabled_shaderpack_hashes=list(dict.fromkeys(data.get("enabled_shaderpack_hashes", []))),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize Profile to a dict suitable for JSON storage."""
        return {
            "id": self.id,
            "name": self.name,
            "instance_id": self.instance_id,
            "instance_path": self.instance_path,
            "minecraft_version": self.minecraft_version,
            "loader": self.loader,
            "loader_version": self.loader_version,
            "enabled_mod_hashes": list(self.enabled_mod_hashes),
            "enabled_resourcepack_hashes": list(self.enabled_resourcepack_hashes),
            "enabled_shaderpack_hashes": list(self.enabled_shaderpack_hashes),
        }
