# Historical Changes

This document tracks major changes to the Chrome Data Extractor project, most recent first.

---

### 11. Deduplication and date rounding
**Date:** 2026-03-17
- **Date format:** All dates rounded to the nearest minute (`YYYY-MM-DD HH:MM`) after sorting, collapsing same-minute visits and reducing near-duplicates across sources.
- **`--deduplicate` / `--no-deduplicate`:** New flag (default on) that deduplicates rows by `(Profile, Date, URL)` keeping the most recent entry. Removed 198 duplicates on first run.

### 10. OneTab IndexedDB support, profile identifiers, sort order
**Date:** 2026-03-17
- **OneTab IDB:** Newer versions of OneTab migrate data from `Local Extension Settings` (LevelDB) to `IndexedDB`. Added a minimal V8 deserializer and custom-comparator trick to open Chrome's `idb_cmp1` LevelDB format. `extract_onetab()` now auto-detects which format is present and dispatches accordingly.
- **Profile identifiers:** `get_profile_identifier()` always includes the folder name (`Profile 1`, `Default`, etc.) combined with the display name from `Preferences` — e.g. `Profile 1 (Your Chrome)` — so duplicate display names across profiles are distinguishable.
- **Sort order:** CSV is sorted most-recent-first. Rows with no date sort to the end.

### 9. Bookmarks and history as primary sources
**Date:** 2026-03-17
- **Bookmarks:** `extract_bookmarks()` reads Chrome's `Bookmarks` JSON, walks the full folder tree, and records the complete folder path in the `Group` column.
- **History:** `extract_history()` copies the SQLite `History` database (plus journal/WAL files for a consistent snapshot) and exports all visited URLs ordered by most recent visit.
- **OneTab demoted to secondary:** Works when data is in the legacy LevelDB format; now gracefully auto-upgrades to IDB path (see entry 10).
- **`Source` column added:** Each row is tagged `Bookmark`, `History`, or `OneTab`.
- **`--bookmarks` / `--history` / `--onetab` flags:** Toggle each source independently (all on by default).
- **Output renamed:** Default filename changed from `YYYY_MM_DD_OneTabOutput.csv` to `YYYY_MM_DD_ChromeExport.csv`.

### 8. Multi-profile support and `.env` configuration
**Date:** 2026-03-17
- **`--all-profiles` / `--no-all-profiles`:** Scans all Chrome profiles by default. Each profile is identified by reading the display name from its `Preferences` file, falling back to the folder name.
- **`--chrome-dir`:** Runtime override for the Chrome user data directory.
- **`CHROME_DIR` env var:** Added alongside existing `PLATFORM`, `ONETAB_PATH`, and `OUTPUT_DIR`.
- **`.env.example`:** Documents all configuration variables with platform-specific defaults.
- **Cross-platform paths:** Auto-detected for macOS, Linux, and Windows.

### 7. `.env` and cross-platform path configuration
**Date:** 2026-03-17
- **`python-dotenv` added:** Script loads `.env` on startup.
- **`get_default_onetab_path()`:** Returns the correct OneTab LevelDB path for macOS, Linux, or Windows based on `PLATFORM` env var or `sys.platform` auto-detection.
- **`.env.example` created:** Template with all configurable variables.
- **`.env` added to `.gitignore`.**

### 6. SSH key setup and GitHub push
**Date:** 2026-03-17
- Generated `ed25519` SSH key, added to GitHub, switched remote from HTTPS to SSH.
- Added `github.com` to `known_hosts`.

### 5. Repository consolidation and feature planning
**Date:** 2026-02-18
- Merged `LICENSE` from remote `origin/main` using `--allow-unrelated-histories`.
- Defined strategy for expanding extractor to include Bookmarks, Open Tabs, and a unified CSV format.

### 4. Path handling refactor
**Date:** 2026-02-18
- Refactored all path handling to use `pathlib.Path`.
- Introduced `DEFAULT_ONETAB_PATH` as a `Path` object.

### 3. Output and documentation refinements
**Date:** 2026-02-15
- Moved documentation files into `human_readable_documentation/`.
- Updated output logic to use CWD as default output location.
- Added full CLI flag documentation to `README.md`.
- Ran `uv sync` with explicit compiler flags to fix `plyvel-ci` / LevelDB compatibility.

### 2. Project relocation and path resolution
**Date:** February 2026
- Project moved from `/Users/curtisoneal/OneTabExtractor/` to a new location; fixed hardcoded paths and IDE configuration.
- Switched to dynamic path resolution (`os.path.dirname(os.path.abspath(__file__))`).

### 1. LevelDB and plyvel linking fixes
**Date:** February 2026
- Resolved `ImportError` / `dlopen` symbol not found (`__ZTIN7leveldb10ComparatorE`) on macOS.
- Fixed by compiling with explicit `LDFLAGS`/`CPPFLAGS` and baking in rpath. Switched to `plyvel-ci` for better maintenance.
