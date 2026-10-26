"""Load the user manual shown by the Help menu."""

import sys
from pathlib import Path

from services.localization import SUPPORTED_LOCALES


def _find_manual_dir() -> Path:
    """Find the directory containing manual HTML files across dev and frozen environments."""
    # 1. Check PyInstaller temp bundle directory (_MEIPASS)
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            cand = Path(meipass) / "docs"
            if cand.is_dir():
                return cand
        # Check next to the executable
        exe_dir = Path(sys.executable).resolve().parent / "docs"
        if exe_dir.is_dir():
            return exe_dir

    # 2. Check parent directories relative to this file (dev / repo root)
    for parent in Path(__file__).resolve().parents:
        cand = parent / "docs"
        if cand.is_dir() and (cand / "manual_en.html").is_file():
            return cand

    # 3. Check current working directory
    cwd_cand = Path.cwd() / "docs"
    if cwd_cand.is_dir() and (cwd_cand / "manual_en.html").is_file():
        return cwd_cand

    cwd_sub = Path.cwd() / "MainOrganizer" / "docs"
    if cwd_sub.is_dir() and (cwd_sub / "manual_en.html").is_file():
        return cwd_sub

    # Default fallback
    return Path(__file__).resolve().parents[1] / "docs"


MANUAL_DIR = _find_manual_dir()
DEFAULT_LOCALE = "en"


def manual_path(locale: str = DEFAULT_LOCALE) -> Path:
    """Return the localized manual path, falling back to English."""
    manual_dir = _find_manual_dir()
    selected_locale = locale if locale in SUPPORTED_LOCALES else DEFAULT_LOCALE
    localized_path = manual_dir / f"manual_{selected_locale}.html"
    if localized_path.is_file():
        return localized_path
    english_path = manual_dir / "manual_en.html"
    if english_path.is_file():
        return english_path
    return localized_path


def load_manual_html(locale: str = DEFAULT_LOCALE) -> str:
    """Return the manual for *locale*, with a safe English fallback."""
    try:
        path = manual_path(locale)
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except OSError:
        pass

    # Safe fallback if docs could not be loaded
    is_ru = (locale == "ru" or locale == "uk")
    title = "Руководство пользователя MineOrganizer" if is_ru else "MineOrganizer User Manual"
    msg = (
        "Файл руководства пользователя не найден в каталоге приложения. Пожалуйста, проверьте наличие папки docs."
        if is_ru
        else "The manual file could not be loaded. Please check that the docs directory is present."
    )
    return (
        f"<!DOCTYPE html><html><head><meta charset='utf-8'>"
        f"<style>body {{ font-family: system-ui, sans-serif; padding: 24px; line-height: 1.6; color: #333; }} "
        f"h1 {{ color: #2b5797; }} .warn {{ border-left: 4px solid #e74c3c; padding: 12px; background: #fdf2f2; }}</style>"
        f"</head><body><h1>{title}</h1><div class='warn'><p>{msg}</p></div></body></html>"
    )

