"""Parser and analyzer for Minecraft crash reports and game logs."""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CrashAnalysis:
    """Diagnostic outcome for a Minecraft crash report or log file."""

    file_path: Path
    file_type: str  # "crash_report" or "log"
    timestamp: str = ""
    title: str = ""
    category: str = "unknown"  # "out_of_memory", "java_version", "missing_dependency", "mixin_conflict", "duplicate_mod", "driver_opengl", "mod_exception", "unknown"
    summary: str = ""
    recommendation: str = ""
    suspected_mods: list[str] = field(default_factory=list)
    exception_class: str = ""
    exception_message: str = ""
    minecraft_version: str = ""
    java_version: str = ""
    raw_text: str = ""


# Common package to mod-name heuristics for stack trace inspection
KNOWN_PACKAGE_MODS: dict[str, str] = {
    "me.jellysquid.mods.sodium": "Sodium",
    "net.coderbot.iris": "Iris Shaders",
    "me.jellysquid.mods.lithium": "Lithium",
    "me.jellysquid.mods.phosphor": "Phosphor",
    "me.jellysquid.mods.indium": "Indium",
    "link.infra.indium": "Indium",
    "net.fabricmc.fabric": "Fabric API",
    "com.mojang.blaze3d": "Minecraft Engine (OpenGL)",
    "vazkii.botania": "Botania",
    "vazkii.quark": "Quark",
    "mezz.jei": "JEI (Just Enough Items)",
    "appeng": "Applied Energistics 2",
    "blusunrize.immersiveengineering": "Immersive Engineering",
    "mekanism": "Mekanism",
    "com.simibubi.create": "Create",
    "pie.ilikepiefoo.quark": "Quark",
    "dev.latvian.mods": "Latvian Mod",
    "embeddedt.embeddium": "Embeddium",
    "org.embeddedt.embeddium": "Embeddium",
    "xaero": "Xaero's Minimap / World Map",
    "journeymap": "JourneyMap",
}


def find_game_root(instance_path: Path) -> Path:
    """Find the root Minecraft directory containing logs, crash-reports, or mods."""
    for root in (instance_path / ".minecraft", instance_path / "minecraft", instance_path):
        if (root / "logs").is_dir() or (root / "crash-reports").is_dir() or (root / "mods").is_dir():
            return root
    return instance_path


def list_available_log_files(instance_path: Path) -> list[tuple[str, Path]]:
    """Return available crash reports and log files sorted by modification time (newest first)."""
    game_root = find_game_root(instance_path)
    entries: list[tuple[str, Path]] = []

    # Crash reports
    crash_dir = game_root / "crash-reports"
    if crash_dir.is_dir():
        try:
            for item in crash_dir.iterdir():
                if item.is_file() and item.name.startswith("crash-") and item.suffix == ".txt":
                    label = f"Crash Report: {item.name}"
                    entries.append((label, item))
        except OSError:
            pass

    # Logs
    logs_dir = game_root / "logs"
    if logs_dir.is_dir():
        for name in ("latest.log", "debug.log"):
            log_file = logs_dir / name
            if log_file.is_file():
                entries.append((f"Log: {name}", log_file))

    # Sort newest files first
    def _mtime_key(pair: tuple[str, Path]) -> tuple[float, str]:
        try:
            return (pair[1].stat().st_mtime, pair[1].name)
        except OSError:
            return (0.0, "")

    entries.sort(key=_mtime_key, reverse=True)
    return entries


def analyze_log_content(
    content: str,
    file_path: Path,
    file_type: str = "crash_report",
    known_mod_names: list[str] | None = None,
) -> CrashAnalysis:
    """Analyze crash report or latest log text and produce structured diagnosis."""
    analysis = CrashAnalysis(file_path=file_path, file_type=file_type, raw_text=content)

    # 1. Extract Minecraft version & Java version if available in system details
    mc_ver_match = re.search(r"Minecraft Version:\s*([^\r\n]+)", content)
    if mc_ver_match:
        analysis.minecraft_version = mc_ver_match.group(1).strip()

    java_ver_match = re.search(r"Java Version:\s*([^\r\n]+)", content)
    if java_ver_match:
        analysis.java_version = java_ver_match.group(1).strip()

    time_match = re.search(r"Time:\s*([^\r\n]+)", content)
    if time_match:
        analysis.timestamp = time_match.group(1).strip()

    desc_match = re.search(r"Description:\s*([^\r\n]+)", content)
    if desc_match:
        analysis.title = desc_match.group(1).strip()

    # 2. Check for "Suspected Mods" section (common in Fabric/ModernFix/Forge crash reports)
    suspected_section_match = re.search(
        r"(?:-- Suspected Mods --|Suspected Mods:)(.*?)(?:\n\s*\n|--|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if suspected_section_match:
        raw_suspected = suspected_section_match.group(1)
        # Parse mod titles or IDs like "Sodium (sodium), Version: 0.5.8" or "mod_id"
        for line in raw_suspected.strip().splitlines():
            cleaned = line.strip().lstrip("-\t* ")
            if not cleaned:
                continue
            name_part = cleaned.split(",")[0].strip()
            name_match = re.match(r"^([^()]+)", name_part)
            if name_match:
                mod_label = name_match.group(1).strip()
                if mod_label and mod_label not in analysis.suspected_mods:
                    analysis.suspected_mods.append(mod_label)

    # 3. Check Out of Memory
    if "java.lang.OutOfMemoryError" in content or "GC overhead limit exceeded" in content:
        analysis.category = "out_of_memory"
        analysis.title = analysis.title or "Out of Memory (Java heap space)"
        analysis.exception_class = "java.lang.OutOfMemoryError"
        analysis.summary = "The game ran out of allocated memory (RAM)."
        analysis.recommendation = (
            "Increase allocated RAM in your launcher settings (for example, allocate 4 GB to 6 GB). "
            "Ensure you are running 64-bit Java."
        )
        return analysis

    # 4. Check Java class version mismatch
    java_class_match = re.search(
        r"UnsupportedClassVersionError:.*?compiled by a more recent version of the Java Runtime \(class file version (\d+)\.0\).*?only recognizes.*?up to (\d+)\.0",
        content,
        re.DOTALL,
    )
    if java_class_match:
        required_class = int(java_class_match.group(1))
        current_class = int(java_class_match.group(2))
        class_to_java = {52: "8", 55: "11", 60: "16", 61: "17", 65: "21", 69: "25"}
        req_java = class_to_java.get(required_class, f"Java class {required_class}")
        cur_java = class_to_java.get(current_class, f"Java class {current_class}")

        analysis.category = "java_version"
        analysis.title = "Java Version Incompatibility"
        analysis.exception_class = "java.lang.UnsupportedClassVersionError"
        analysis.summary = (
            f"A mod requires Java {req_java}, but Minecraft was launched using Java {cur_java}."
        )
        analysis.recommendation = (
            f"Install and select Java {req_java} (or newer) in your launcher settings."
        )
        return analysis

    # 5. Check Missing dependencies
    missing_deps_match = re.search(
        r"(?:Some of your mods are incomplete and require additional mods|Missing or unsupported mandatory dependencies|Mod.*?requires.*?:)(.*?)(?:\n\s*\n|--|\Z)",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if missing_deps_match and ("requires" in missing_deps_match.group(0).lower() or "missing" in missing_deps_match.group(0).lower()):
        analysis.category = "missing_dependency"
        analysis.title = "Missing Mod Dependencies"
        analysis.summary = "The game failed to launch because required mod dependencies are missing."
        missing_text = missing_deps_match.group(0).strip()
        analysis.recommendation = (
            f"Install the missing dependencies listed below:\n{missing_text[:300]}"
        )
        # Try to extract required mod names
        for req in re.findall(r"requires\s+['\"]?([a-zA-Z0-9_\-]+)", missing_text):
            if req.lower() not in {"minecraft", "fabric", "forge", "neoforge"} and req not in analysis.suspected_mods:
                analysis.suspected_mods.append(req)
        return analysis

    # 6. Check Duplicate Mods
    dup_match = re.search(
        r"(?:Duplicate mods? found with id|Duplicate mods? found for|Duplicate mod ID|Duplicate mods? found)[\s:\"\']+([a-zA-Z0-9_\-]+)",
        content,
        re.IGNORECASE,
    )
    if dup_match:
        dup_mod = dup_match.group(1)
        analysis.category = "duplicate_mod"
        analysis.title = f"Duplicate Mod Detected: {dup_mod}"
        analysis.summary = f'Multiple files with the same mod ID "{dup_mod}" were found in your mods folder.'
        analysis.recommendation = f'Remove older or duplicate jar files for "{dup_mod}" from the mods directory.'
        if dup_mod not in analysis.suspected_mods:
            analysis.suspected_mods.append(dup_mod)
        return analysis

    # 7. Check OpenGL / Graphics driver errors
    if "org.lwjgl.opengl.OpenGLException" in content or "GLFW error 65542" in content or "WGL: The driver does not appear to support OpenGL" in content:
        analysis.category = "driver_opengl"
        analysis.title = "Graphics / OpenGL Driver Error"
        analysis.summary = "The graphics driver failed to initialize OpenGL."
        analysis.recommendation = (
            "Update your graphics card drivers (NVIDIA, AMD, or Intel). "
            "If you have dual GPUs, ensure the game is set to run on the dedicated GPU."
        )
        return analysis

    # 8. Check Mixin transformer / injection error
    if "org.spongepowered.asm.mixin" in content:
        analysis.category = "mixin_conflict"
        analysis.title = analysis.title or "Mixin Injection Conflict"
        analysis.summary = "A mod failed to inject bytecode into the game (Mixin conflict)."

        # Try to locate the mixing mod or target
        mixin_match = re.search(r"in class \[(.*?)\]", content)
        target_info = f" in {mixin_match.group(1)}" if mixin_match else ""

        # Scan for known packages in the mixin stack trace
        for pkg, mod_name in KNOWN_PACKAGE_MODS.items():
            if pkg in content and mod_name not in analysis.suspected_mods:
                analysis.suspected_mods.append(mod_name)

        if analysis.suspected_mods:
            mod_names_str = ", ".join(analysis.suspected_mods[:3])
            analysis.recommendation = (
                f"Conflict detected involving {mod_names_str}{target_info}. "
                "Try updating these mods to the latest version or test removing them one by one."
            )
        else:
            analysis.recommendation = (
                f"Two or more mods conflict while modifying the same game code{target_info}. "
                "Check for mod updates or remove recently added mods."
            )
        return analysis

    # 9. Generic Caused by: exception extraction
    caused_by_matches = re.findall(r"Caused by:\s*([a-zA-Z0-9_\.]+(?:Exception|Error|Throwable))(?::\s*([^\r\n]+))?", content)
    if caused_by_matches:
        last_cause = caused_by_matches[-1]
        analysis.exception_class = last_cause[0]
        analysis.exception_message = last_cause[1].strip() if len(last_cause) > 1 and last_cause[1] else ""
        analysis.category = "mod_exception"
        analysis.title = f"Crash caused by {analysis.exception_class.split('.')[-1]}"
        analysis.summary = f"{analysis.exception_class}: {analysis.exception_message}" if analysis.exception_message else analysis.exception_class

        # Scan stack trace for known mod packages
        for pkg, mod_name in KNOWN_PACKAGE_MODS.items():
            if pkg in content and mod_name not in analysis.suspected_mods:
                analysis.suspected_mods.append(mod_name)

        # Also match with provided user mod names/IDs
        if known_mod_names:
            for mod_n in known_mod_names:
                if len(mod_n) > 3 and mod_n.lower() in content.lower() and mod_n not in analysis.suspected_mods:
                    analysis.suspected_mods.append(mod_n)

        if analysis.suspected_mods:
            analysis.recommendation = (
                f"The crash trace indicates an issue related to: {', '.join(analysis.suspected_mods[:4])}. "
                "Check that these mods match your Minecraft and loader version."
            )
        else:
            analysis.recommendation = (
                "Review the full stack trace below to identify the failing mod or library."
            )
        return analysis

    # 10. Fallback for logs without standard crash header
    if file_type == "log":
        fatal_lines = [line.strip() for line in content.splitlines() if "[FATAL]" in line or "[ERROR]" in line]
        if fatal_lines:
            analysis.category = "mod_exception"
            analysis.title = "Errors Found in Log"
            analysis.summary = fatal_lines[-1][:200]
            analysis.recommendation = "Review the highlighted error lines in the log viewer."
            return analysis

    analysis.category = "unknown"
    analysis.title = analysis.title or "Unknown Game Crash"
    analysis.summary = "No standard crash signatures were matched."
    analysis.recommendation = "Examine the raw log or crash report for details."
    return analysis


def analyze_instance_logs(
    instance_path: Path,
    known_mod_names: list[str] | None = None,
) -> CrashAnalysis | None:
    """Find the most recent crash report or log for an instance and analyze it."""
    log_files = list_available_log_files(instance_path)
    if not log_files:
        return None

    # Prefer newest crash report if one exists
    crash_reports = [pair for pair in log_files if "crash-" in pair[1].name]
    target_pair = crash_reports[0] if crash_reports else log_files[0]
    selected_label, selected_path = target_pair
    try:
        content = selected_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    file_type = "crash_report" if "crash-" in selected_path.name else "log"
    return analyze_log_content(content, selected_path, file_type, known_mod_names)
