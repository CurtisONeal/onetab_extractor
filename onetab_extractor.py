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
import sqlite3
import sys
import os
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

load_dotenv()

console = Console()

ONETAB_EXTENSION_ID = 'chphlpgkkbolifaimnlloiipkdnihall'
CHROME_EPOCH = datetime(1601, 1, 1)
CSV_FIELDS = ['Profile', 'Source', 'Group', 'Date', 'Color', 'Title', 'URL']


# ---------------------------------------------------------------------------
# Platform helpers
# ---------------------------------------------------------------------------

def get_chrome_dir() -> Path:
    env_val = os.getenv('CHROME_DIR', '')
    if env_val:
        return Path(env_val).expanduser()

    platform = os.getenv('PLATFORM', '').lower()
    if platform == 'windows' or (not platform and sys.platform == 'win32'):
        local_app_data = os.getenv('LOCALAPPDATA', r'C:\Users\Default\AppData\Local')
        return Path(local_app_data) / 'Google' / 'Chrome' / 'User Data'
    elif platform == 'linux' or (not platform and sys.platform.startswith('linux')):
        return Path('~/.config/google-chrome').expanduser()
    else:
        return Path('~/Library/Application Support/Google/Chrome').expanduser()


def chrome_time_to_str(micros: int) -> str:
    """Convert Chrome/Windows FILETIME (microseconds since 1601-01-01) to a readable string."""
    if not micros:
        return ''
    try:
        return (CHROME_EPOCH + timedelta(microseconds=micros)).strftime('%Y-%m-%d %H:%M:%S')
    except (OverflowError, ValueError):
        return ''


# ---------------------------------------------------------------------------
# Profile discovery
# ---------------------------------------------------------------------------

def get_profile_name(profile_dir: Path) -> str:
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


def find_profiles(chrome_dir: Path) -> list[tuple[Path, str]]:
    """Return (profile_dir, profile_name) for every directory that has Chrome data."""
    results = []
    try:
        candidates = sorted(chrome_dir.iterdir())
    except Exception as e:
        console.print(f"[bold red]Cannot read Chrome directory:[/bold red] {e}")
        return results

    for item in candidates:
        if not item.is_dir():
            continue
        has_data = (
            (item / 'Bookmarks').exists()
            or (item / 'History').exists()
            or (item / 'Local Extension Settings' / ONETAB_EXTENSION_ID).exists()
        )
        if has_data:
            results.append((item, get_profile_name(item)))

    return results


# ---------------------------------------------------------------------------
# Extractors
# ---------------------------------------------------------------------------

def extract_bookmarks(profile_dir: Path, profile_name: str) -> list[dict]:
    bookmarks_path = profile_dir / 'Bookmarks'
    if not bookmarks_path.exists():
        return []

    try:
        with open(bookmarks_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        console.print(f"[yellow]Could not read bookmarks for '{profile_name}': {e}[/yellow]")
        return []

    tabs = []

    def walk(node: dict, folder: str) -> None:
        if node.get('type') == 'url':
            tabs.append({
                'Profile': profile_name,
                'Source': 'Bookmark',
                'Group': folder,
                'Date': chrome_time_to_str(int(node.get('date_added', 0))),
                'Color': '',
                'Title': node.get('name', 'No Title'),
                'URL': node.get('url', ''),
            })
        elif node.get('type') == 'folder':
            child_folder = f"{folder}/{node['name']}" if folder else node['name']
            for child in node.get('children', []):
                walk(child, child_folder)

    ROOT_LABELS = {
        'bookmark_bar': 'Bookmarks Bar',
        'other': 'Other Bookmarks',
        'synced': 'Mobile Bookmarks',
    }
    for root_key, root_node in data.get('roots', {}).items():
        if isinstance(root_node, dict):
            walk(root_node, ROOT_LABELS.get(root_key, root_key))

    return tabs


def extract_history(profile_dir: Path, profile_name: str,
                    tmp_base: Path, keep_tmp: bool) -> list[dict]:
    history_path = profile_dir / 'History'
    if not history_path.exists():
        return []

    safe_name = profile_name.replace(' ', '_').replace('/', '_')
    tmp_history = tmp_base / f'tmp_history_{safe_name}'

    try:
        shutil.copy2(history_path, tmp_history)
    except Exception as e:
        console.print(f"[bold red]Error copying History for '{profile_name}':[/bold red] {e}")
        return []

    tabs = []
    try:
        conn = sqlite3.connect(str(tmp_history))
        rows = conn.execute(
            'SELECT title, url, last_visit_time FROM urls ORDER BY last_visit_time DESC'
        ).fetchall()
        conn.close()
        for title, url, last_visit in rows:
            tabs.append({
                'Profile': profile_name,
                'Source': 'History',
                'Group': '',
                'Date': chrome_time_to_str(last_visit),
                'Color': '',
                'Title': title or 'No Title',
                'URL': url or '',
            })
    except Exception as e:
        console.print(f"[bold red]Error reading History for '{profile_name}':[/bold red] {e}")
    finally:
        if not keep_tmp and tmp_history.exists():
            tmp_history.unlink()

    return tabs


def extract_onetab(profile_dir: Path, profile_name: str,
                   tmp_base: Path, keep_tmp: bool) -> list[dict]:
    db_path = profile_dir / 'Local Extension Settings' / ONETAB_EXTENSION_ID
    if not db_path.exists():
        return []

    safe_name = profile_name.replace(' ', '_').replace('/', '_')
    tmp_db = tmp_base / f'tmp_onetab_{safe_name}'

    try:
        if tmp_db.exists():
            shutil.rmtree(tmp_db)
        shutil.copytree(db_path, tmp_db)
    except Exception as e:
        console.print(f"[bold red]Error copying OneTab DB for '{profile_name}':[/bold red] {e}")
        return []

    tabs = []
    try:
        db = plyvel.DB(str(tmp_db), create_if_missing=False)
        raw_state = db.get(b'state')
        migrated = db.get(b'stateMigratedToIDB')
        db.close()

        if migrated:
            console.print(
                f"[yellow]OneTab in '{profile_name}' has migrated to IndexedDB "
                f"(not yet supported — skipping).[/yellow]"
            )
            return []

        if not raw_state:
            return []

        state_data = json.loads(json.loads(raw_state.decode('utf-8')))

        for group in state_data.get('tabGroups', []):
            label = group.get('label') or 'Untitled Group'
            create_date = group.get('createDate')
            date_str = datetime.fromtimestamp(create_date / 1000).strftime('%Y-%m-%d %H:%M:%S') if create_date else ''
            color = group.get('color', '')
            group_type = group.get('groupType', '')

            for tab in group.get('tabsMeta', []):
                tabs.append({
                    'Profile': profile_name,
                    'Source': 'OneTab',
                    'Group': f"{label} [{group_type}]" if group_type else label,
                    'Date': date_str,
                    'Color': color,
                    'Title': tab.get('title', 'No Title'),
                    'URL': tab.get('url', ''),
                })

    except Exception as e:
        console.print(f"[bold red]Error reading OneTab for '{profile_name}':[/bold red] {e}")
    finally:
        if not keep_tmp and tmp_db.exists():
            shutil.rmtree(tmp_db)

    return tabs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    chrome_dir = get_chrome_dir()

    parser = argparse.ArgumentParser(
        description='Export Chrome bookmarks, history, and OneTab data to CSV.')

    # Directory / path
    parser.add_argument('--chrome-dir', type=str, default=str(chrome_dir),
                        help='Chrome user data directory')

    # Profile selection
    parser.add_argument('--all-profiles', action=argparse.BooleanOptionalAction, default=True,
                        help='Scan all profiles (default: on). --no-all-profiles uses Default only.')

    # Source selection
    parser.add_argument('--bookmarks', action=argparse.BooleanOptionalAction, default=True,
                        help='Include bookmarks (default: on)')
    parser.add_argument('--history', action=argparse.BooleanOptionalAction, default=True,
                        help='Include browsing history (default: on)')
    parser.add_argument('--onetab', action=argparse.BooleanOptionalAction, default=True,
                        help='Include OneTab data if available (default: on)')

    # Output
    parser.add_argument('-o', '--output', type=str, help='CSV filename')
    parser.add_argument('-d', '--dir', type=str,
                        default=os.getenv('OUTPUT_DIR') or None,
                        help='Output directory (defaults to OUTPUT_DIR env var or CWD)')

    # Flags
    parser.add_argument('-dr', '--dryrun', action='store_true',
                        help='Count rows without writing a file')
    parser.add_argument('-p', '--print', action='store_true',
                        help='Pretty-print first 20 rows to terminal')
    parser.add_argument('--keep-tmp', action='store_true',
                        help='Keep temporary database copies after export')

    args = parser.parse_args()

    project_dir = Path(args.dir).resolve() if args.dir else Path.cwd()
    resolved_chrome_dir = Path(args.chrome_dir).expanduser()

    # Resolve profiles to process
    if args.all_profiles:
        profiles = find_profiles(resolved_chrome_dir)
        if not profiles:
            console.print(f"[bold yellow]No Chrome profiles found under:[/bold yellow] {resolved_chrome_dir}")
            return
        console.print(f"Found [bold]{len(profiles)}[/bold] profile(s).")
    else:
        default_dir = resolved_chrome_dir / 'Default'
        profiles = [(default_dir, get_profile_name(default_dir))]

    # Extract from all profiles and sources
    all_rows = []
    for profile_dir, profile_name in profiles:
        if args.bookmarks:
            rows = extract_bookmarks(profile_dir, profile_name)
            if rows:
                console.print(f"  [dim]{profile_name}[/dim] bookmarks: [cyan]{len(rows)}[/cyan]")
            all_rows.extend(rows)

        if args.history:
            rows = extract_history(profile_dir, profile_name, project_dir, args.keep_tmp)
            if rows:
                console.print(f"  [dim]{profile_name}[/dim] history:   [cyan]{len(rows)}[/cyan]")
            all_rows.extend(rows)

        if args.onetab:
            rows = extract_onetab(profile_dir, profile_name, project_dir, args.keep_tmp)
            if rows:
                console.print(f"  [dim]{profile_name}[/dim] onetab:    [cyan]{len(rows)}[/cyan]")
            all_rows.extend(rows)

    if args.dryrun:
        source_counts = {}
        for row in all_rows:
            source_counts[row['Source']] = source_counts.get(row['Source'], 0) + 1
        breakdown = '  '.join(f"[bold]{s}[/bold]: {n}" for s, n in sorted(source_counts.items()))
        console.print(Panel(
            f"[bold cyan]{len(all_rows)}[/bold cyan] total rows across "
            f"{len(profiles)} profile(s)\n{breakdown}"))
        return

    date_str = datetime.now().strftime('%Y_%m_%d')
    filename = args.output if args.output else f"{date_str}_ChromeExport.csv"
    full_output_path = project_dir / filename

    with open(full_output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    console.print(
        f"\n[bold green]Success![/bold green] Exported [bold cyan]{len(all_rows)}[/bold cyan] rows "
        f"to [underline]{full_output_path}[/underline]")

    if args.print:
        table = Table(title="Chrome Export Preview", expand=False)
        table.add_column("Profile", style="white", max_width=12, overflow="fold")
        table.add_column("Source", style="blue", max_width=10)
        table.add_column("Group", style="magenta", max_width=18, overflow="fold")
        table.add_column("Date", style="yellow", max_width=19)
        table.add_column("Title", style="cyan", max_width=28, overflow="fold")
        table.add_column("URL", style="green", max_width=38, overflow="fold")

        for item in all_rows[:20]:
            table.add_row(item['Profile'], item['Source'], item['Group'],
                          item['Date'], item['Title'], item['URL'])

        console.print(table)
        if len(all_rows) > 20:
            console.print(f"... and {len(all_rows) - 20} more rows.")


if __name__ == "__main__":
    main()
