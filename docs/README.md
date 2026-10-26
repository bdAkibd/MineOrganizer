# MineOrganizer Documentation & Manuals

This directory contains the user manuals displayed within the application (`Help → About` / `ManualDialog`) in all supported languages.

## Canonical Manual Workflow

To keep all documentation consistent, maintainable, and aligned:

1. **English is the single canonical source of truth**:
   - Always make content updates, additions, and edits in [`manual_en.html`](manual_en.html) first.
   - Use clean semantic HTML (`<h1>`, `<h2>`, `<h3>`, `<p>`, `<ol>`, `<ul>`, `<code>`, `<p class="note">`).

2. **Translate to other supported languages**:
   - Update [`manual_ru.html`](manual_ru.html) and all other locale files (`manual_<locale>.html`).
   - Keep identical HTML section hierarchy and tag structure so that navigation and styling remain consistent across all languages.

3. **Validate structural alignment**:
   - Run the synchronization check script:
     ```powershell
     python docs/sync_manuals.py --check
     ```
   - The script verifies that heading tags, lists, and structural counts across all 10 translations match `manual_en.html` 1:1.

## Supported Locales

| Locale | Language | File |
|---|---|---|
| `en` | English (Canonical) | `manual_en.html` |
| `ru` | Russian | `manual_ru.html` |
| `uk` | Ukrainian | `manual_uk.html` |
| `de` | German | `manual_de.html` |
| `es` | Spanish | `manual_es.html` |
| `fr` | French | `manual_fr.html` |
| `it` | Italian | `manual_it.html` |
| `ja` | Japanese | `manual_ja.html` |
| `pt` | Portuguese | `manual_pt.html` |
| `zh_CN` | Simplified Chinese | `manual_zh_CN.html` |
| `zh_TW` | Traditional Chinese | `manual_zh_TW.html` |
