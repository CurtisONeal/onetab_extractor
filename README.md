# OneTab Link Extractor

Extracts saved tab groups from the [OneTab](https://www.one-tab.com/) Chrome extension's LevelDB database and exports them to a CSV file with optional terminal preview.

Supports all Chrome profiles in one pass by default, and works on macOS, Linux, and Windows.

---

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)** — handles the virtual environment and dependencies automatically
- **LevelDB** headers/libraries (required to compile `plyvel-ci`)

  ```bash
  # macOS
  brew install leveldb
  ```

  On Linux, install `libleveldb-dev` via your package manager. On Windows, `plyvel-ci` ships pre-built wheels so no extra step is needed.

---

## Setup

### 1. Clone and configure

```bash
git clone <repo-url>
cd onetab_extractor
cp .env.example .env
```

Edit `.env` if you need to override any defaults (see [Configuration](#configuration) below). For most users on macOS the defaults work without any changes.

### 2. Sync dependencies

```bash
# Intel Mac / Linux
LDFLAGS="-L/usr/local/lib" CPPFLAGS="-I/usr/local/include" uv sync

# Apple Silicon Mac
LDFLAGS="-L/opt/homebrew/lib" CPPFLAGS="-I/opt/homebrew/include" uv sync
```

> The build flags are needed so `plyvel-ci` links correctly against LevelDB. They are already encoded in `pyproject.toml` for both Homebrew prefixes, but passing them explicitly at sync time is the safest approach.

---

## Usage

```bash
uv run onetab_extractor.py [flags]
```

By default the script scans **all Chrome profiles**, combines every tab into one CSV, and writes it to the current directory as `YYYY_MM_DD_OneTabOutput.csv`.

### Common examples

```bash
# Export all profiles (default behaviour)
uv run onetab_extractor.py

# Dry run — count tabs and groups without writing a file
uv run onetab_extractor.py -dr

# Terminal preview of the first 20 rows
uv run onetab_extractor.py -p

# Export to a specific file and directory
uv run onetab_extractor.py -o my_tabs.csv -d ~/Desktop

# Export only the Default profile
uv run onetab_extractor.py --no-all-profiles

# Point at a non-standard Chrome directory
uv run onetab_extractor.py --chrome-dir "/Volumes/Backup/Chrome User Data"

# Target one specific LevelDB path directly
uv run onetab_extractor.py --path "~/Library/Application Support/Google/Chrome/Profile 1/Local Extension Settings/chphlpgkkbolifaimnlloiipkdnihall"
```

### All flags

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--chrome-dir` | Chrome user data directory to scan for profiles | Platform default (see below) |
| `--all-profiles` / `--no-all-profiles` | Scan all profiles vs. Default profile only | `--all-profiles` |
| `--path` | Explicit path to a single OneTab LevelDB; bypasses profile discovery | — |
| `-o`, `--output` | CSV filename | `YYYY_MM_DD_OneTabOutput.csv` |
| `-d`, `--dir` | Output directory | `OUTPUT_DIR` env var, or CWD |
| `-dr`, `--dryrun` | Count tabs/groups without writing a file | off |
| `-p`, `--print` | Pretty-print first 20 rows to the terminal | off |
| `--keep-tmp` | Keep temporary database copies after export | off |

---

## Configuration

Copy `.env.example` to `.env` and set any values you need. All are optional.

| Variable | Description | Default |
| :--- | :--- | :--- |
| `PLATFORM` | Force platform detection (`mac`, `linux`, `windows`) | Auto-detected |
| `CHROME_DIR` | Chrome user data directory | Platform default (see below) |
| `ONETAB_PATH` | Override path to a single OneTab LevelDB | Derived from `CHROME_DIR` |
| `OUTPUT_DIR` | Default output directory for the CSV | Current working directory |

### Default Chrome directories by platform

| Platform | Path |
| :--- | :--- |
| macOS | `~/Library/Application Support/Google/Chrome` |
| Linux | `~/.config/google-chrome` |
| Windows | `%LOCALAPPDATA%\Google\Chrome\User Data` |

---

## CSV output

Each row represents one saved tab. The `Profile` column contains the display name read from Chrome's `Preferences` file, or the folder name (`Profile 1`, `Profile 7`, etc.) if no name is found.

| Column | Description |
| :--- | :--- |
| `Profile` | Chrome profile name or folder name |
| `Group` | OneTab group label (or "Untitled Group") |
| `Date Saved` | Timestamp the group was created (`YYYY-MM-DD HH:MM:SS`) |
| `Color` | Color tag assigned in OneTab |
| `Group Type` | Group type metadata from OneTab |
| `Title` | Page title |
| `URL` | Full URL |

---

## Troubleshooting

**Database copy fails / Chrome lock error**
The script copies the LevelDB before reading it to avoid conflicts with Chrome. If Chrome is mid-write, the copy may fail. Close Chrome and retry, or use `--keep-tmp` to inspect the copied database.

**`dlopen` / symbol not found error**
Rebuild `plyvel-ci` with the correct Homebrew prefix:

```bash
# Intel Mac
LDFLAGS="-L/usr/local/lib" CPPFLAGS="-I/usr/local/include" uv sync --reinstall-package plyvel-ci

# Apple Silicon
LDFLAGS="-L/opt/homebrew/lib" CPPFLAGS="-I/opt/homebrew/include" uv sync --reinstall-package plyvel-ci
```

**No OneTab data found**
Verify the extension is installed and has data, then check the Chrome directory:

```
~/Library/Application Support/Google/Chrome/<profile>/Local Extension Settings/chphlpgkkbolifaimnlloiipkdnihall/
```

The folder should contain `.ldb` and `.log` files.

---

## Dependencies

| Package | Purpose |
| :--- | :--- |
| `plyvel-ci` | LevelDB access (maintained `plyvel` fork) |
| `python-dotenv` | `.env` file loading |
| `rich` | Terminal formatting and preview tables |
| `hatchling` | Build backend |
