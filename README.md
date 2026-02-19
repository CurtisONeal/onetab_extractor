

# Browser Data Extractor (macOS)

This tool extracts browser data from multiple sources (OneTab, Bookmarks, and Open Tabs) and exports them to a unified human-readable CSV format with rich terminal preview support.

## 🚀 Features
- **Unified Extraction:** Consolidates data from:
    - **OneTab Extension:** Tab groups and saved tabs from LevelDB.
    - **Chrome Bookmarks:** Hierarchical parsing of the JSON Bookmarks file.
    - **Open Tabs (Live):** Captures all open tabs across ALL Chrome windows via AppleScript (macOS).
    - **History & Search:** Extracts recent browsing history and specific Google/Chrome search terms from SQLite.
- **Standardized Schema:** Exports to a consistent format for all sources.
- **Rich Terminal UI:** Pretty-print previews with color-coded sources.

## Exported Data Structure
The unified CSV export includes:
- **Source**: Where the data came from (OneTab, Bookmark, Open Tab)
- **Category/Group**: The tab group label or bookmark folder path
- **Title**: Page title
- **URL**: Full URL
- **Date Added**: When the item was created/saved
- **Color**: Visual group color (if available)
- **Metadata**: Source-specific extra data (JSON formatted, sparse)

## Usage
Run the script using `uv run` or your configured alias.

```bash
uv run onetab_extractor.py
```

### Command-Line Flags
| Flag | Description | Default |
| :--- | :--- | :--- |
| `--onetab-path` | OneTab LevelDB path | Standard Chrome path |
| `--bookmarks-path` | Chrome Bookmarks path | Standard Chrome path |
| `--sessions-path` | Chrome Sessions path | Standard Chrome path |
| `--history-path` | Chrome History SQLite path | Standard Chrome path |
| `--history-limit` | Max history items to extract | `500` |
| `-o`, `--output` | CSV filename | `YYYY_MM_DD_UnifiedBrowserData.csv` |
| `-d`, `--dir` | Output directory | Current Working Directory |
| `-dr`, `--dryrun` | Count rows without exporting | `False` |
| `-p`, `--print` | Pretty print a preview table | `False` |

### Examples
- **Full Preview**: `uv run onetab_extractor.py -p -dr`
- **Custom Directory**: `uv run onetab_extractor.py -d ~/Downloads`

---

## ⚠️ Configuration
If you use a different macOS user or an Apple Silicon Mac, you may need to update paths.

### 1. File Paths (`onetab_extractor.py`)
Within the script, paths are resolved relative to the Chrome profile.
* **`--onetab-path`**: Defaults to the standard OneTab extension path.
* **`--bookmarks-path`**: Defaults to the standard Chrome Bookmarks file.
* **`--sessions-path`**: Defaults to the standard Chrome Sessions directory.
* **`--dir`**: Defaults to the current working directory for output.

### 2. Build Paths (`pyproject.toml`)
The `uv` configuration contains hardcoded paths for the C++ compiler to find Homebrew libraries:
* **`--include-dirs` / `--library-dirs`**: Currently set to `/usr/local/include` and `/usr/local/lib` for Intel Macs. If moving to an Apple Silicon (M1/M2/M3) Mac, these usually change to `/opt/homebrew/include` and `/opt/homebrew/lib`.

### 3. Shell Alias (`.zshrc`)
The alias used to call the script relies on an absolute path to the project directory:
* `alias getOneTab="uv --directory  /Users/curtisoneal/dev/gitrepos/personal/learning/OneTabExtractor run onetab_extractor.py"`
* **Action**: Update `/Users/curtisoneal/` to your actual macOS username.

---

## Pre-requisites
* **Python**: Version 3.12 or higher.
* **Homebrew Dependencies**: `plyvel-ci` requires LevelDB C++ headers and binaries to compile and link successfully.
    ```bash
    brew install leveldb
    ```

# Setup & Build
This project uses **uv** for high-performance dependency management.

1.  **Initialize the Environment**:
    ```bash
    LDFLAGS="-L/usr/local/lib" CPPFLAGS="-I/usr/local/include" uv sync
    ```

    > **Note**: The build flags ensure `plyvel-ci` links correctly against LevelDB. For Apple Silicon Macs, use `/opt/homebrew/lib` and `/opt/homebrew/include` instead.


# Usage
Run the script using the configured alias or `uv run`.

* **Standard Export**: Generates a CSV in the project folder named `YYYY_MM_DD_OneTabOutput.csv`.
    ```bash
    getOneTab
    ```

### Command-Line Flags
The script supports several flags to customize its behavior:

| Flag | Long Form | Description | Default |
| :--- | :--- | :--- | :--- |
| `--path` | `--path` | Source OneTab LevelDB path | `~/Library/Application Support/...` |
| `-o` | `--output` | CSV filename | `YYYY_MM_DD_OneTabOutput.csv` |
| `-d` | `--dir` | Output directory | Current Working Directory |
| `-dr` | `--dryrun` | Count rows without exporting to CSV | `False` |
| `-p` | `--print` | Pretty print a preview table to terminal | `False` |
| | `--keep-tmp` | Do not delete the temporary database copy | `False` |

### Examples

* **Dry Run**: Counts the number of tabs and groups without creating a file.
    ```bash
    getOneTab -dr
    ```
* **Terminal Preview**: Displays a formatted table of the first 20 tabs.
    ```bash
    getOneTab -p
    ```
* **Custom Output**: Save to a specific file and directory.
    ```bash
    getOneTab -o my_tabs.csv -d ~/Desktop
    ```

## Troubleshooting
* **Database Lock**: The script automatically creates a temporary copy in `tmp_onetab_db` to avoid conflicts with Chrome. If Chrome is in the middle of a heavy write operation, the copy might fail; close Chrome if errors persist.
* **ImportError**: If you see a `dlopen` error regarding "symbol not found," rebuild the environment:
    ```bash
    LDFLAGS="-L/usr/local/lib" CPPFLAGS="-I/usr/local/include" uv sync --reinstall-package plyvel-ci
    ```

## OneTab Database Locations

> **Important**: OneTab data is identified by the extension ID `chphlpgkkbolifaimnlloiipkdnihall`. The database contains `.ldb` and `.log` files.

### Primary Location (Default):
```
~/Library/Application Support/Google/Chrome/Default/Local Extension Settings/chphlpgkkbolifaimnlloiipkdnihall/
```

### Extension Files Location:
```
~/Library/Application Support/Google/Chrome/Default/Extensions/chphlpgkkbolifaimnlloiipkdnihall
```

### Alternative Location (Older Chrome versions):
```
~/Library/Application Support/Google/Chrome/Default/Local Storage/leveldb/
```

## Dependencies
The project uses:
- **plyvel-ci**: Maintained fork of plyvel for LevelDB access
- **rich**: Terminal formatting and tables
- **hatchling**: Build backend
