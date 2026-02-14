

# OneTab Link Extractor (macOS)

This tool extracts saved tab groups from the OneTab Chrome extension's binary LevelDB database and exports them to a human-readable CSV format or a terminal preview.

## ⚠️ Local Variable & Customization Concerns
If you move this project to a new machine or use a different macOS user account, the following variables **must** be updated to ensure the script finds your data and the compiler finds the necessary libraries.

### 1. File Paths (`onetab_extractor.py`)
Within the script, two main paths are defaulted to a specific user profile:
* **`--path`**: Defaults to `~/Library/Application Support/Google/Chrome/Default/Local Extension Settings/chphlpgkkbolifaimnlloiipkdnihall`. If you use a different Chrome profile (e.g., "Profile 1"), this must be updated in the code or passed as a flag.
* **`--dir`**: Defaults to `~/OneTabExtractor`. Update this to match your absolute project directory.

### 2. Build Paths (`pyproject.toml`)
The `uv` configuration contains hardcoded paths for the C++ compiler to find Homebrew libraries:
* **`--include-dirs` / `--library-dirs`**: Currently set to `/usr/local/include` and `/usr/local/lib` for Intel Macs. If moving to an Apple Silicon (M1/M2/M3) Mac, these usually change to `/opt/homebrew/include` and `/opt/homebrew/lib`.

### 3. Shell Alias (`.zshrc`)
The alias used to call the script relies on an absolute path to the project directory:
* `alias getOneTab="DYLD_FALLBACK_LIBRARY_PATH='/usr/local/lib' uv --directory /Users/curtisoneal/OneTabExtractor run onetab_extractor.py"`
* **Action**: Update `/Users/curtisoneal/` to your actual macOS username.

---

## Pre-requisites
* **Python**: Version 3.12 or higher.
* **Homebrew Dependencies**: `plyvel` requires C++ headers and binaries to compile and link successfully.
    ```bash
    brew install leveldb snappy
    ```

# Setup & Build
This project uses **uv** for high-performance dependency management. 

1.  **Initialize the Environment**:
    ```bash
    uv sync
    ```
2.  **Handle Linking Errors (Intel Mac)**:
    If you encounter a "symbol not found" error during the build, run the following to bake the library paths into the binary:
    ```bash
    LDFLAGS="-L/usr/local/lib -Wl,-rpath,/usr/local/lib" CPPFLAGS="-I/usr/local/include" uv sync
    ```

## Usage
Run the script using the configured alias or `uv run`.

* **Standard Export**: Generates a CSV in the project folder named `YYYY_MM_DD_OneTabOutput.csv`.
    ```bash
    getOneTab
    ```
* **Dry Run**: Counts the number of tabs and groups without creating a file.
    ```bash
    getOneTab -dr
    ```
* **Terminal Preview**: Displays a formatted table of the first 20 tabs.
    ```bash
    getOneTab -p
    ```

## Troubleshooting
* **Database Lock**: The script automatically creates a "Live Copy" in `tmp_onetab_db` to avoid conflicts with Chrome. If Chrome is in the middle of a heavy write operation, the copy might fail; close Chrome if errors persist.
* **ImportError**: If you see a `dlopen` error regarding a "flat namespace" or "symbol not found," ensure your environment or alias includes `DYLD_FALLBACK_LIBRARY_PATH='/usr/local/lib'`.

Pre-requisites & Assumptions
Snappy Requirement: On macOS, plyvel often requires snappy to be installed via Homebrew to handle compressed Chrome data.

Database Lock: As discussed, you must either close Chrome or copy the database folder to a temporary location before running this, as LevelDB only allows one process to hold a LOCK file at a time.

1. The Python Script (~/onetab_extractor.py)
Verify that the following packages are installed:
- plyvel Because we're dealing with binary LevelDB data
- snappy plyvel often requires snappy
- json
- csv for the output
- os
-  sys
- argparse for the flags
- datetime import datetime

## On my Intel system you can find the OneTab files here:
~/Library/Application Support/Google/Chrome/Default/Extensions/chphlpgkkbolifaimnlloiipkdnihall

If you are looking to backup or recover your actual saved tabs, they are stored in a LevelDB database. Depending on your version of Chrome, they live in one of these two hidden folders:

### Primary Location:
~/Library/Application Support/Google/Chrome/Default/Local Extension Settings/chphlpgkkbolifaimnlloiipkdnihall/

### Alternative Location:
~/Library/Application Support/Google/Chrome/Default/Local Storage/leveldb/

# [!IMPORTANT]
OneTab data is primarily identified by the ID chphlpgkkbolifaimnlloiipkdnihall. Inside the Local Extension Settings folder, you will see .ldb and .log files; these are the actual files that contain your links.
