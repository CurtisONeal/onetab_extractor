# Historical Changes

This document tracks major improvements and fixes documented in the `../OneTabExtractor` project.

## Summary of Improvements

### 7. Metadata Column Refined
**Date:** 2026-02-18
- **Schema Update:** Added a dedicated `Color` column to the unified CSV to promote frequently used metadata.
- **Metadata Sparsity:** Refactored `Metadata` to be sparsely populated, only containing truly source-specific extra data (like `guid` for bookmarks or `groupType` for OneTab).
- **Cleanup:** Empty metadata fields are now exported as empty strings rather than empty JSON objects.
- **Open Tabs:** Updated the placeholder to be more informative and consistent with the new schema.

### 6. Unified Browser Data Extraction
- **New Features:**
    - **Bookmarks:** Added `extract_bookmarks()` to parse Chrome's JSON Bookmarks file.
    - **Open Tabs:** Added `extract_open_tabs()` as a placeholder/skeleton for session extraction.
    - **OneTab:** Refactored OneTab logic into `extract_onetab()`.
- **Unified Schema:** All sources now export to a single CSV with columns: `Source`, `Category/Group`, `Title`, `URL`, `Date Added`, and `Metadata`.
- **Architecture:** The script is now modular, allowing easy addition of more sources or improvements to existing ones (like full SNSS parsing for open tabs).

### 5. Repository Consolidation & Feature Planning
**Date:** 2026-02-18
- **Repository:** Merged `LICENSE` from remote `origin/main` into local `main` branch using `--allow-unrelated-histories`.
- **Feature Strategy:** Defined mechanisms for expanding the extractor to include:
    - **Bookmarks:** Parsing Chrome's JSON `Bookmarks` file.
    - **Open Tabs & Groups:** Parsing binary session files in `~/Library/Application Support/Google/Chrome/Default/Sessions/`.
    - **Normalization:** Proposed a unified CSV structure to combine OneTab, Bookmarks, and Open Tabs data.
- **Branching:** Preparing to branch for the implementation of these new extraction features.

### 4. Path Handling Refactor
**Date:** 2026-02-18
- **`onetab_extractor.py`:** Refactored the script to use `pathlib.Path` objects for all path manipulations instead of strings and `os.path`. 
- **Configuration:** Introduced `DEFAULT_ONETAB_PATH` as a `Path` object to simplify future configuration and user customization.
- **Documentation:** Updated `README.md` to reflect the transition to `pathlib.Path`.

### 3. Recent Updates & Refinements
**Date:** 2026-02-15
- **File Organization:** Moved `Gemini_attempts_to_fix_summary.md` to `human_readable_documentation/` and created `Historical_changes.md`.
- **Output Logic:** Updated `onetab_extractor.py` to use the **Current Working Directory (CWD)** as the default output location. This ensures that when running the script via `uv` or an alias from the project root, the CSV is placed in the project root by default.
- **Documentation:** Added a detailed "Command-Line Flags" section to `README.md` explaining all available arguments (`--path`, `--output`, `--dir`, `--dryrun`, `--print`, `--keep-tmp`).
- **Environment:** Performed `uv sync` with explicit compiler flags to ensure `plyvel-ci` compatibility with LevelDB.

### 2. Project Relocation and Path Resolution
**File:** `moved_directory_confustion.md`
**Date:** February 2026
- **Issue:** Project files moved from `/Users/curtisoneal/OneTabExtractor/` to `/Users/curtisoneal/dev/gitrepos/reference/OneTabExtractor/`, causing IDE configuration and script output errors.
- **Improvements:**
    - **`onetab_extractor.py`:** Updated the script to use dynamic path resolution (`os.path.dirname(os.path.abspath(__file__))`) for the default directory, making the script location-independent.
    - **IDE Configuration:** Guidelines for re-opening the project to allow the IDE to recognize the new `.idea` folder location.
    - **Shell Alias:** Updated the recommended shell alias to point to the new project shortcut.
    - **README.md:** Updated to reflect the code changes and the new alias paths.

### 1. LevelDB and Plyvel Linking Fixes
**File:** `Gemini_attempts_to_fix_summary.md`
**Date:** February 2026
- **Issue:** Persistent `ImportError` during `dlopen()`: symbol not found in flat namespace `__ZTIN7leveldb10ComparatorE` when importing `plyvel`.
- **Root Cause:** Communication breakdown between the Python extension and the LevelDB library on macOS, specifically missing RTTI (Run-Time Type Information) symbols in the Homebrew-installed LevelDB.
- **Solution:** 
    - Attempted forced compilation with `LDFLAGS` and `CPPFLAGS`.
    - Used `install_name_tool` to fix library paths.
    - Ultimately recommended "baking" the rpath into the binary using:
      `LDFLAGS="-L/usr/local/lib -Wl,-rpath,/usr/local/lib" CPPFLAGS="-I/usr/local/include" uv sync`
    - Suggested switching to `plyvel-ci` for better maintenance and handling of these issues.
