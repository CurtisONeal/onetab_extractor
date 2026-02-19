

# OneTab Link Extractor (macOS)

This tool extracts saved tab groups from the OneTab Chrome extension's binary LevelDB database and exports them to a human-readable CSV format with rich terminal preview support.

## 🚀 Current Project State
We have successfully consolidated the repository, pulled in the LICENSE, and are now branching to implement new features:
- **Unified Extraction:** Moving beyond OneTab to also extract Chrome **Bookmarks** and **Open Tabs/Groups**.
- **Data Normalization:** Combining all browser data into a single, standardized CSV format.

## Exported Data
1. The CSV export includes:
- **Group**: Tab group name (or "Untitled Group")
- **Date Saved**: When the tab group was created
- **Color**: Color tag assigned in OneTab (if any)
- **Group Type**: Type of tab group
- **Title**: Page title
- **URL**: Full URL
2. The csv will output the the location of the script. In my case this is:
~/dev/gitrepos/personal/learning/OneTabExtractor/2026_02_15_OneTabOutput.csv

# Initial Setup:

## ⚠️ Local Variable & Customization Concerns
If you move this project to a new machine or use a different macOS user account, the following variables **must** be updated to ensure the script finds your data and the compiler finds the necessary libraries.

### 1. File Paths (`onetab_extractor.py`)
Within the script, the main path is defaulted to a specific user profile using `pathlib.Path`:
* **`--path`**: Defaults to the standard OneTab extension path in your home directory. This is now managed as a `Path` object in the code for easier configuration.
* **`--dir`**: Defaults to the current working directory. You can override this with the `-d` or `--dir` flag.

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
