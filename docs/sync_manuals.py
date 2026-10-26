#!/usr/bin/env python3
"""Sync and validation tool for localized MineOrganizer user manuals.

The canonical source of truth for the user manual is manual_en.html.
When editing documentation:
1. Make changes to manual_en.html first.
2. Run this script to verify structural alignment across all supported locales:
       python docs/sync_manuals.py --check
3. Update the corresponding manual_<locale>.html files with translations.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent
CANONICAL_MANUAL = DOCS_DIR / "manual_en.html"
SUPPORTED_LOCALES = ("ru", "de", "es", "fr", "uk", "it", "zh_CN", "zh_TW", "ja", "pt")


def extract_headings(html_text: str) -> list[tuple[str, str]]:
    """Extract list of (tag, inner_text) for all h1, h2, h3 tags."""
    pattern = re.compile(r"<(h[1-3])\b[^>]*>(.*?)</\1>", re.IGNORECASE | re.DOTALL)
    headings = []
    for match in pattern.finditer(html_text):
        tag = match.group(1).lower()
        text = re.sub(r"<[^>]+>", "", match.group(2)).strip()
        headings.append((tag, text))
    return headings


def validate_manual(locale: str) -> list[str]:
    """Validate that manual_<locale>.html matches manual_en.html structurally."""
    errors: list[str] = []
    loc_file = DOCS_DIR / f"manual_{locale}.html"
    if not loc_file.is_file():
        return [f"File {loc_file.name} is missing!"]

    en_content = CANONICAL_MANUAL.read_text(encoding="utf-8")
    loc_content = loc_file.read_text(encoding="utf-8")

    en_headings = extract_headings(en_content)
    loc_headings = extract_headings(loc_content)

    if len(en_headings) != len(loc_headings):
        errors.append(
            f"Heading count mismatch in {loc_file.name}: "
            f"found {len(loc_headings)}, expected {len(en_headings)} from manual_en.html"
        )
    else:
        for idx, ((en_tag, _), (loc_tag, loc_text)) in enumerate(zip(en_headings, loc_headings)):
            if en_tag != loc_tag:
                errors.append(
                    f"Heading #{idx + 1} tag mismatch in {loc_file.name}: "
                    f"<{loc_tag}> '{loc_text}' vs expected <{en_tag}>"
                )

    en_ol_count = en_content.count("<ol>")
    loc_ol_count = loc_content.count("<ol>")
    if en_ol_count != loc_ol_count:
        errors.append(
            f"<ol> count mismatch in {loc_file.name}: {loc_ol_count} vs {en_ol_count}"
        )

    en_ul_count = en_content.count("<ul>")
    loc_ul_count = loc_content.count("<ul>")
    if en_ul_count != loc_ul_count:
        errors.append(
            f"<ul> count mismatch in {loc_file.name}: {loc_ul_count} vs {en_ul_count}"
        )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify manual localizations against canonical manual_en.html"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check alignment of all language manuals and exit with non-zero code on failure",
    )
    args = parser.parse_args()

    if not CANONICAL_MANUAL.is_file():
        print(f"Error: Canonical manual {CANONICAL_MANUAL} not found!", file=sys.stderr)
        return 1

    total_errors = 0
    en_headings = extract_headings(CANONICAL_MANUAL.read_text(encoding="utf-8"))
    print(f"Canonical manual: manual_en.html ({len(en_headings)} headings)")

    for locale in SUPPORTED_LOCALES:
        errs = validate_manual(locale)
        if errs:
            print(f"[{locale.upper()}] FAIL:")
            for err in errs:
                print(f"  - {err}")
            total_errors += len(errs)
        else:
            print(f"[{locale.upper()}] OK - perfectly aligned with manual_en.html")

    if total_errors > 0:
        print(f"\nValidation failed with {total_errors} structural error(s).", file=sys.stderr)
        return 1

    print("\nAll localized manuals are 100% structurally aligned with manual_en.html!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
