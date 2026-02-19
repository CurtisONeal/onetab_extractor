# Historical Changes

This document tracks major improvements and fixes documented in the `../OneTabExtractor` project.

## Summary of Improvements

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

### 2. Project Relocation and Path Resolution
**File:** `moved_directory_confustion.md`
**Date:** February 2026
- **Issue:** Project files moved from `/Users/curtisoneal/OneTabExtractor/` to `/Users/curtisoneal/dev/gitrepos/reference/OneTabExtractor/`, causing IDE configuration and script output errors.
- **Improvements:**
    - **`onetab_extractor.py`:** Updated the script to use dynamic path resolution (`os.path.dirname(os.path.abspath(__file__))`) for the default directory, making the script location-independent.
    - **IDE Configuration:** Guidelines for re-opening the project to allow the IDE to recognize the new `.idea` folder location.
    - **Shell Alias:** Updated the recommended shell alias to point to the new project shortcut.
    - **README.md:** Updated to reflect the code changes and the new alias paths.

### 3. Recent Updates & Refinements
**Date:** 2026-02-15
- **File Organization:** Moved `Gemini_attempts_to_fix_summary.md` to `human_readable_documentation/` and created `Historical_changes.md`.
- **Output Logic:** Updated `onetab_extractor.py` to use the **Current Working Directory (CWD)** as the default output location. This ensures that when running the script via `uv` or an alias from the project root, the CSV is placed in the project root by default.
- **Documentation:** Added a detailed "Command-Line Flags" section to `README.md` explaining all available arguments (`--path`, `--output`, `--dir`, `--dryrun`, `--print`, `--keep-tmp`).
- **Environment:** Performed `uv sync` with explicit compiler flags to ensure `plyvel-ci` compatibility with LevelDB.

### 4. Path Handling Refactor
**Date:** 2026-02-18
- **`onetab_extractor.py`:** Refactored the script to use `pathlib.Path` objects for all path manipulations instead of strings and `os.path`. 
- **Configuration:** Introduced `DEFAULT_ONETAB_PATH` as a `Path` object to simplify future configuration and user customization.
- **Documentation:** Updated `README.md` to reflect the transition to `pathlib.Path`.
