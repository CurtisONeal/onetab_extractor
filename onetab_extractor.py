#!/usr/bin/env -S uv run --quiet
# /// script
# dependencies = [
#   "plyvel-ci",
#   "rich",
#   "python-dotenv",
# ]
# requires-python = ">=3.12"
# ///

import plyvel
import json
import csv
import shutil
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

load_dotenv()

console = Console()

ONETAB_EXTENSION_ID = 'chphlpgkkbolifaimnlloiipkdnihall'
CSV_FIELDS = ['Profile', 'Group', 'Date Saved', 'Color', 'Group Type', 'Title', 'URL']


def get_chrome_dir() -> Path:
    """Return the Chrome user data directory based on platform."""
    env_val = os.getenv('CHROME_DIR', '')
    if env_val:
        return Path(env_val).expanduser()

    platform = os.getenv('PLATFORM', '').lower()
    if platform == 'windows' or (not platform and sys.platform == 'win32'):
        local_app_data = os.getenv('LOCALAPPDATA', r'C:\Users\Default\AppData\Local')
        return Path(local_app_data) / 'Google' / 'Chrome' / 'User Data'
    elif platform == 'linux' or (not platform and sys.platform.startswith('linux')):
        return Path('~/.config/google-chrome').expanduser()
    else:  # mac (default)
        return Path('~/Library/Application Support/Google/Chrome').expanduser()


def get_default_onetab_path(chrome_dir: Path) -> Path:
    """Return the single-profile fallback LevelDB path (Default profile)."""
    env_path = os.getenv('ONETAB_PATH', '')
    if env_path:
        return Path(env_path).expanduser()
    return chrome_dir / 'Default' / 'Local Extension Settings' / ONETAB_EXTENSION_ID


def get_profile_name(profile_dir: Path) -> str:
    """Read the display name from Chrome Preferences; fall back to folder name."""
    prefs_path = profile_dir / 'Preferences'
    try:
        with open(prefs_path, 'r', encoding='utf-8') as f:
            prefs = json.load(f)
        name = prefs.get('profile', {}).get('name', '').strip()
        if name:
            return name
    except Exception:
        pass
    return profile_dir.name


def find_onetab_profiles(chrome_dir: Path) -> list[tuple[Path, str]]:
    """Return (onetab_db_path, profile_name) for every profile that has OneTab data."""
    results = []
    try:
        candidates = sorted(chrome_dir.iterdir())
    except Exception as e:
        console.print(f"[bold red]Cannot read Chrome directory:[/bold red] {e}")
        return results

    for item in candidates:
        if not item.is_dir():
            continue
        onetab_path = item / 'Local Extension Settings' / ONETAB_EXTENSION_ID
        if onetab_path.exists():
            results.append((onetab_path, get_profile_name(item)))

    return results


def extract_tabs(db_path: Path, profile_name: str, tmp_base: Path, keep_tmp: bool) -> list[dict]:
    """Copy LevelDB to a temp dir, extract tabs, clean up. Returns list of tab dicts."""
    safe_name = profile_name.replace(' ', '_').replace('/', '_')
    tmp_db = tmp_base / f'tmp_onetab_{safe_name}'

    try:
        if tmp_db.exists():
            shutil.rmtree(tmp_db)
        shutil.copytree(db_path, tmp_db)
    except Exception as e:
        console.print(f"[bold red]Error copying database for '{profile_name}':[/bold red] {e}")
        return []

    tabs = []
    try:
        db = plyvel.DB(str(tmp_db), create_if_missing=False)
        raw_state = db.get(b'state')

        if not raw_state:
            console.print(f"[yellow]No 'state' key in '{profile_name}' — skipping.[/yellow]")
            return []

        state_data = json.loads(json.loads(raw_state.decode('utf-8')))

        for group in state_data.get('tabGroups', []):
            label = group.get('label') or 'Untitled Group'
            create_date = group.get('createDate')
            date_saved = datetime.fromtimestamp(create_date / 1000).strftime('%Y-%m-%d %H:%M:%S') if create_date else ''
            color = group.get('color', '')
            group_type = group.get('groupType', '')

            for tab in group.get('tabsMeta', []):
                tabs.append({
                    'Profile': profile_name,
                    'Group': label,
                    'Date Saved': date_saved,
                    'Color': color,
                    'Group Type': group_type,
                    'Title': tab.get('title', 'No Title'),
                    'URL': tab.get('url', ''),
                })

        db.close()
    except Exception as e:
        console.print(f"[bold red]Error reading database for '{profile_name}':[/bold red] {e}")
    finally:
        if not keep_tmp and tmp_db.exists():
            shutil.rmtree(tmp_db)

    return tabs


def main():
    chrome_dir = get_chrome_dir()

    parser = argparse.ArgumentParser(description='Extract OneTab links via uv.')

    # Directory / path configuration
    parser.add_argument('--chrome-dir', type=str,
                        default=str(chrome_dir),
                        help='Chrome user data directory containing profile folders')
    parser.add_argument('--path', type=str,
                        default=None,
                        help='Explicit single OneTab LevelDB path (skips profile discovery)')

    # Profile selection
    parser.add_argument('--all-profiles', action=argparse.BooleanOptionalAction, default=True,
                        help='Scan all profiles in --chrome-dir (default: on). '
                             'Use --no-all-profiles to export only the Default profile.')

    # Output configuration
    parser.add_argument('-o', '--output', type=str, help='CSV filename')
    parser.add_argument('-d', '--dir', type=str,
                        default=os.getenv('OUTPUT_DIR') or None,
                        help='Output directory (defaults to OUTPUT_DIR env var or current working directory)')

    # Flags
    parser.add_argument('-dr', '--dryrun', action='store_true', help='Count rows without exporting')
    parser.add_argument('-p', '--print', action='store_true', help='Pretty print the results to terminal')
    parser.add_argument('--keep-tmp', action='store_true', help='Do not delete temporary database copies')

    args = parser.parse_args()

    # Resolve output directory
    project_dir = Path(args.dir).resolve() if args.dir else Path.cwd()
    resolved_chrome_dir = Path(args.chrome_dir).expanduser()

    # Build list of (db_path, profile_name) to process
    if args.path:
        # Explicit single path — derive profile name from its grandparent folder
        db_path = Path(args.path).expanduser()
        targets = [(db_path, get_profile_name(db_path.parent.parent))]
    elif args.all_profiles:
        targets = find_onetab_profiles(resolved_chrome_dir)
        if not targets:
            console.print(f"[bold yellow]No OneTab data found in any profile under:[/bold yellow] {resolved_chrome_dir}")
            return
        console.print(f"Found [bold]{len(targets)}[/bold] profile(s) with OneTab data.")
    else:
        db_path = get_default_onetab_path(resolved_chrome_dir)
        targets = [(db_path, get_profile_name(db_path.parent.parent))]

    # Extract tabs from all targets
    all_tabs = []
    for db_path, profile_name in targets:
        tabs = extract_tabs(db_path, profile_name, project_dir, args.keep_tmp)
        all_tabs.extend(tabs)

    if args.dryrun:
        group_count = len({(t['Profile'], t['Group']) for t in all_tabs})
        console.print(Panel(
            f"Found [bold cyan]{len(all_tabs)}[/bold cyan] tabs across "
            f"{group_count} groups in {len(targets)} profile(s)."))
        return

    date_str = datetime.now().strftime('%Y_%m_%d')
    filename = args.output if args.output else f"{date_str}_OneTabOutput.csv"
    full_output_path = project_dir / filename

    with open(full_output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_tabs)

    console.print(
        f"[bold green]Success![/bold green] Exported [bold cyan]{len(all_tabs)}[/bold cyan] tabs "
        f"to [underline]{full_output_path}[/underline]")

    if args.print:
        table = Table(title="OneTab Extraction Preview", expand=False)
        table.add_column("Profile", style="white", max_width=15, overflow="fold")
        table.add_column("Group", style="magenta", max_width=20, overflow="fold")
        table.add_column("Date Saved", style="yellow", max_width=19)
        table.add_column("Color", style="blue", max_width=10)
        table.add_column("Title", style="cyan", max_width=30, overflow="fold")
        table.add_column("URL", style="green", max_width=40, overflow="fold")

        for item in all_tabs[:20]:
            table.add_row(item['Profile'], item['Group'], item['Date Saved'],
                          item['Color'], item['Title'], item['URL'])

        console.print(table)
        if len(all_tabs) > 20:
            console.print(f"... and {len(all_tabs) - 20} more rows.")


if __name__ == "__main__":
    main()
