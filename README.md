# Chrome Data Extractor

Exports Chrome **bookmarks**, **browsing history**, and **OneTab** saved tabs from all Chrome profiles into a single CSV file. Supports macOS, Linux, and Windows.

---

## What it extracts

| Source | Data | Notes |
| :--- | :--- | :--- |
| **Bookmarks** | All bookmarks with full folder path | Primary |
| **History** | All visited URLs ordered by most recent | Primary |
| **OneTab** | Saved tab groups with labels and colors | Secondary — skipped if OneTab has migrated to IndexedDB (newer installs) |

---

## Prerequisites

- **Python 3.12+**
- **[uv](https://docs.astral.sh/uv/)**
- **LevelDB** headers/libraries (needed to compile `plyvel-ci` for OneTab support)

  ```bash
  # macOS
  brew install leveldb
  ```

  On Linux, install `libleveldb-dev` via your package manager. On Windows, `plyvel-ci` ships pre-built wheels.

---

## Setup

```bash
git clone <repo-url>
cd onetab_extractor
cp .env.example .env
```

Edit `.env` only if you need to override defaults — most users on macOS need no changes.

### Sync dependencies

```bash
# Intel Mac / Linux
LDFLAGS="-L/usr/local/lib" CPPFLAGS="-I/usr/local/include" uv sync

# Apple Silicon Mac
LDFLAGS="-L/opt/homebrew/lib" CPPFLAGS="-I/opt/homebrew/include" uv sync
```

---

## Usage

```bash
uv run onetab_extractor.py [flags]
```

Default behaviour: scans **all Chrome profiles**, exports bookmarks + history + OneTab (if available) into `YYYY_MM_DD_ChromeExport.csv` in the current directory.

### Common examples

```bash
# Export everything (default)
uv run onetab_extractor.py

# Dry run — count rows by source without writing a file
uv run onetab_extractor.py -dr

# Terminal preview of first 20 rows
uv run onetab_extractor.py -p

# Bookmarks only
uv run onetab_extractor.py --no-history --no-onetab

# History only, single profile (Default)
uv run onetab_extractor.py --no-bookmarks --no-onetab --no-all-profiles

# Save to a specific file and directory
uv run onetab_extractor.py -o my_export.csv -d ~/Desktop

# Point at a non-standard Chrome installation
uv run onetab_extractor.py --chrome-dir "/Volumes/Backup/Chrome User Data"
```

### All flags

| Flag | Description | Default |
| :--- | :--- | :--- |
| `--chrome-dir` | Chrome user data directory | Platform default (see below) |
| `--all-profiles` / `--no-all-profiles` | Scan all profiles vs. Default only | `--all-profiles` |
| `--bookmarks` / `--no-bookmarks` | Include bookmarks | on |
| `--history` / `--no-history` | Include browsing history | on |
| `--onetab` / `--no-onetab` | Include OneTab data if available | on |
| `-o`, `--output` | CSV filename | `YYYY_MM_DD_ChromeExport.csv` |
| `-d`, `--dir` | Output directory | `OUTPUT_DIR` env var, or CWD |
| `-dr`, `--dryrun` | Count rows by source without writing a file | off |
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

Each row is one URL. The `Source` column identifies where it came from.

| Column | Description |
| :--- | :--- |
| `Profile` | Chrome profile display name, or folder name (`Profile 1`, `Profile 7`, etc.) |
| `Source` | `Bookmark`, `History`, or `OneTab` |
| `Group` | Bookmark folder path (e.g. `Bookmarks Bar/Dev/Tools`), OneTab group label, or blank for history |
| `Date` | Date added (bookmarks), last visited (history), or group created (OneTab) |
| `Color` | OneTab color tag — blank for other sources |
| `Title` | Page title |
| `URL` | Full URL |

---

## Troubleshooting

**OneTab shows "migrated to IndexedDB — skipping"**
Newer versions of OneTab moved their storage from LevelDB to IndexedDB. IndexedDB support is not yet implemented. The rest of the export (bookmarks and history) still runs normally.

**Database copy fails / Chrome lock error**
The script copies all databases before reading to avoid conflicts with a running Chrome. Close Chrome and retry, or use `--keep-tmp` to inspect the copies.

**`dlopen` / symbol not found error**
Rebuild `plyvel-ci` with the correct Homebrew prefix:

```bash
# Intel Mac
LDFLAGS="-L/usr/local/lib" CPPFLAGS="-I/usr/local/include" uv sync --reinstall-package plyvel-ci

# Apple Silicon
LDFLAGS="-L/opt/homebrew/lib" CPPFLAGS="-I/opt/homebrew/include" uv sync --reinstall-package plyvel-ci
```

---

## Dependencies

| Package | Purpose |
| :--- | :--- |
| `plyvel-ci` | LevelDB access for OneTab data (maintained `plyvel` fork) |
| `python-dotenv` | `.env` file loading |
| `rich` | Terminal formatting and preview tables |
| `hatchling` | Build backend |
