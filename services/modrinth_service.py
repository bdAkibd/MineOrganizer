"""Integration with the Modrinth API for mod searching, updates, and downloading."""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

USER_AGENT = "MineOrganizer/1.0 (https://github.com/MainOrganizer)"


@dataclass(slots=True)
class ModrinthSearchResult:
    project_id: str
    slug: str
    title: str
    description: str
    author: str
    icon_url: str = ""
    downloads: int = 0
    follows: int = 0
    versions: list[str] = field(default_factory=list)
    loaders: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ModrinthVersionFile:
    url: str
    filename: str
    primary: bool
    size: int
    sha1: str = ""
    sha512: str = ""


@dataclass(slots=True)
class ModrinthDependency:
    project_id: str | None = None
    version_id: str | None = None
    dependency_type: str = "required"  # "required", "optional", "incompatible"
    file_name: str = ""


@dataclass(slots=True)
class ModrinthVersion:
    version_id: str
    project_id: str
    name: str
    version_number: str
    game_versions: list[str] = field(default_factory=list)
    loaders: list[str] = field(default_factory=list)
    files: list[ModrinthVersionFile] = field(default_factory=list)
    dependencies: list[ModrinthDependency] = field(default_factory=list)
    changelog: str = ""


@dataclass(slots=True)
class ModUpdateInfo:
    file_hash: str
    mod_name: str
    current_version: str
    new_version_number: str
    new_version_name: str
    download_url: str
    filename: str
    size: int
    changelog: str = ""


def _api_get(url: str, timeout: int = 6) -> Any:
    """Perform a GET request to the Modrinth API."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _api_post(url: str, payload: dict[str, Any], timeout: int = 8) -> Any:
    """Perform a JSON POST request to the Modrinth API."""
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=data,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def search_modrinth(
    query: str,
    loader: str = "",
    minecraft_version: str = "",
    limit: int = 20,
    offset: int = 0,
) -> list[ModrinthSearchResult]:
    """Search Modrinth mods matching query, loader, and Minecraft version."""
    facets: list[list[str]] = [["project_type:mod"]]
    if loader and loader.lower() not in {"all", "all loaders", "—"}:
        facets.append([f"categories:{loader.lower()}"])
    if minecraft_version and minecraft_version.lower() not in {"all", "all versions", "—"}:
        facets.append([f"versions:{minecraft_version}"])

    params = {
        "query": query.strip(),
        "limit": str(limit),
        "offset": str(offset),
        "facets": json.dumps(facets),
    }
    url = f"https://api.modrinth.com/v2/search?{urllib.parse.urlencode(params)}"
    try:
        data = _api_get(url)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return []

    hits = data.get("hits", []) if isinstance(data, dict) else []
    results: list[ModrinthSearchResult] = []
    for hit in hits:
        if not isinstance(hit, dict):
            continue
        results.append(
            ModrinthSearchResult(
                project_id=str(hit.get("project_id") or ""),
                slug=str(hit.get("slug") or ""),
                title=str(hit.get("title") or ""),
                description=str(hit.get("description") or ""),
                author=str(hit.get("author") or ""),
                icon_url=str(hit.get("icon_url") or ""),
                downloads=int(hit.get("downloads") or 0),
                follows=int(hit.get("follows") or 0),
                versions=[str(v) for v in hit.get("versions", [])],
                loaders=[str(l) for l in hit.get("categories", [])],
            )
        )
    return results


def get_project_versions(
    project_id_or_slug: str,
    loader: str = "",
    minecraft_version: str = "",
) -> list[ModrinthVersion]:
    """Fetch versions for a specific project filtered by loader and version."""
    query_params: dict[str, str] = {}
    if loader and loader.lower() not in {"all", "all loaders", "—"}:
        query_params["loaders"] = json.dumps([loader.lower()])
    if minecraft_version and minecraft_version.lower() not in {"all", "all versions", "—"}:
        query_params["game_versions"] = json.dumps([minecraft_version])

    qs = f"?{urllib.parse.urlencode(query_params)}" if query_params else ""
    url = f"https://api.modrinth.com/v2/project/{urllib.parse.quote(project_id_or_slug)}/version{qs}"
    try:
        data = _api_get(url)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return []

    if not isinstance(data, list):
        return []

    versions: list[ModrinthVersion] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        files: list[ModrinthVersionFile] = []
        for file_info in item.get("files", []):
            if not isinstance(file_info, dict):
                continue
            hashes = file_info.get("hashes", {})
            files.append(
                ModrinthVersionFile(
                    url=str(file_info.get("url") or ""),
                    filename=str(file_info.get("filename") or ""),
                    primary=bool(file_info.get("primary", False)),
                    size=int(file_info.get("size") or 0),
                    sha1=str(hashes.get("sha1") or "") if isinstance(hashes, dict) else "",
                    sha512=str(hashes.get("sha512") or "") if isinstance(hashes, dict) else "",
                )
            )

        dependencies: list[ModrinthDependency] = []
        for dep in item.get("dependencies", []):
            if not isinstance(dep, dict):
                continue
            dependencies.append(
                ModrinthDependency(
                    project_id=dep.get("project_id"),
                    version_id=dep.get("version_id"),
                    dependency_type=str(dep.get("dependency_type") or "required"),
                    file_name=str(dep.get("file_name") or ""),
                )
            )

        versions.append(
            ModrinthVersion(
                version_id=str(item.get("id") or ""),
                project_id=str(item.get("project_id") or ""),
                name=str(item.get("name") or ""),
                version_number=str(item.get("version_number") or ""),
                game_versions=[str(v) for v in item.get("game_versions", [])],
                loaders=[str(l) for l in item.get("loaders", [])],
                files=files,
                dependencies=dependencies,
                changelog=str(item.get("changelog") or ""),
            )
        )
    return versions


def check_mod_updates(
    file_hashes: list[str],
    algorithm: str = "sha1",
    game_versions: list[str] | None = None,
    loaders: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Check Modrinth for newer versions of the specified file hashes."""
    if not file_hashes:
        return {}

    payload: dict[str, Any] = {
        "hashes": file_hashes,
        "algorithm": algorithm,
    }
    if game_versions:
        payload["game_versions"] = [v for v in game_versions if v and v != "—"]
    if loaders:
        payload["loaders"] = [l.lower() for l in loaders if l and l != "—"]

    url = "https://api.modrinth.com/v2/version_files/update"
    try:
        data = _api_post(url, payload)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, ValueError):
        return {}

    return data if isinstance(data, dict) else {}


def download_file(
    url: str,
    destination_path: Path,
    progress_callback: Callable[[int, int], None] | None = None,
) -> Path:
    """Download a file with streaming chunks and optional progress updates."""
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    temp_destination = destination_path.with_suffix(destination_path.suffix + ".download")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    with urllib.request.urlopen(request, timeout=30) as response, temp_destination.open("wb") as output:
        content_length = response.headers.get("Content-Length")
        total_size = int(content_length) if content_length and content_length.isdigit() else 0
        downloaded = 0
        chunk_size = 64 * 1024

        while True:
            chunk = response.read(chunk_size)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            if progress_callback:
                progress_callback(downloaded, total_size)

    temp_destination.replace(destination_path)
    return destination_path
