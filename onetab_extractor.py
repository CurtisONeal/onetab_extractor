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
import struct
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
    if not micros:
        return ''
    try:
        return (CHROME_EPOCH + timedelta(microseconds=micros)).strftime('%Y-%m-%d %H:%M:%S')
    except (OverflowError, ValueError):
        return ''


def ms_epoch_to_str(ms: float) -> str:
    """Convert Unix millisecond timestamp to string."""
    if not ms:
        return ''
    try:
        return datetime.fromtimestamp(ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    except (OSError, OverflowError, ValueError):
        return ''


# ---------------------------------------------------------------------------
# Profile discovery
# ---------------------------------------------------------------------------

def get_profile_identifier(profile_dir: Path) -> str:
    """Return 'FolderName' or 'FolderName (DisplayName)' for a profile directory."""
    folder = profile_dir.name  # always included: 'Default', 'Profile 1', etc.
    prefs_path = profile_dir / 'Preferences'
    try:
        with open(prefs_path, 'r', encoding='utf-8') as f:
            prefs = json.load(f)
        display = prefs.get('profile', {}).get('name', '').strip()
        if display and display != folder:
            return f'{folder} ({display})'
    except Exception:
        pass
    return folder


def find_profiles(chrome_dir: Path) -> list[tuple[Path, str]]:
    results = []
    try:
        candidates = sorted(chrome_dir.iterdir())
    except Exception as e:
        console.print(f'[bold red]Cannot read Chrome directory:[/bold red] {e}')
        return results
    for item in candidates:
        if not item.is_dir():
            continue
        has_data = (
            (item / 'Bookmarks').exists()
            or (item / 'History').exists()
            or (item / 'Local Extension Settings' / ONETAB_EXTENSION_ID).exists()
            or (item / 'IndexedDB' /
                f'chrome-extension_{ONETAB_EXTENSION_ID}_0.indexeddb.leveldb').exists()
        )
        if has_data:
            results.append((item, get_profile_identifier(item)))
    return results


# ---------------------------------------------------------------------------
# Minimal V8 deserializer (for OneTab IndexedDB values)
# ---------------------------------------------------------------------------

def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    result, shift = 0, 0
    while pos < len(data):
        b = data[pos]; pos += 1
        result |= (b & 0x7F) << shift
        if not (b & 0x80):
            return result, pos
        shift += 7
    return result, pos


def _decode_v8(data: bytes, pos: int = 0) -> tuple[any, int]:
    """Decode one V8-serialized value starting at pos. Returns (value, new_pos)."""
    if pos >= len(data):
        return None, pos
    tag = data[pos]; pos += 1

    if tag == 0xFF:                         # version wrapper
        _, pos = _read_varint(data, pos)
        return _decode_v8(data, pos)
    if tag in (0x00, 0x3F):                 # padding / verify-count
        if tag == 0x3F: _, pos = _read_varint(data, pos)
        return _decode_v8(data, pos)
    if tag in (0x5F, 0x30): return None, pos   # undefined / null
    if tag == 0x54: return True, pos           # true
    if tag == 0x46: return False, pos          # false
    if tag == 0x49:                            # int32 zigzag
        n, pos = _read_varint(data, pos)
        return (n >> 1) ^ -(n & 1), pos
    if tag == 0x55:                            # uint32
        n, pos = _read_varint(data, pos)
        return n, pos
    if tag in (0x4E, 0x44):                    # double / date
        return struct.unpack_from('<d', data, pos)[0], pos + 8
    if tag == 0x22:                            # one-byte string
        n, pos = _read_varint(data, pos)
        return data[pos:pos + n].decode('latin-1', errors='replace'), pos + n
    if tag == 0x53:                            # utf-8 string
        n, pos = _read_varint(data, pos)
        return data[pos:pos + n].decode('utf-8', errors='replace'), pos + n
    if tag == 0x63:                            # two-byte string
        n, pos = _read_varint(data, pos)
        return data[pos:pos + n * 2].decode('utf-16-le', errors='replace'), pos + n * 2
    if tag == 0x5E:                            # object reference (skip)
        _, pos = _read_varint(data, pos)
        return None, pos
    if tag == 0x6F:                            # JS object
        obj = {}
        while pos < len(data):
            if data[pos] == 0x7B:              # end '{'
                pos += 1; _, pos = _read_varint(data, pos); break
            k, pos = _decode_v8(data, pos)
            v, pos = _decode_v8(data, pos)
            if isinstance(k, str):
                obj[k] = v
        return obj, pos
    if tag == 0x41:                            # dense array
        n, pos = _read_varint(data, pos)
        arr = []
        for _ in range(n):
            v, pos = _decode_v8(data, pos)
            arr.append(v)
        if pos < len(data) and data[pos] == 0x24:  # end '$'
            pos += 1
            _, pos = _read_varint(data, pos)
            _, pos = _read_varint(data, pos)
        return arr, pos
    if tag == 0x61:                            # sparse array
        length, pos = _read_varint(data, pos)
        arr = []
        while pos < len(data):
            if data[pos] == 0x40:              # end '@'
                pos += 1
                _, pos = _read_varint(data, pos)
                _, pos = _read_varint(data, pos)
                break
            k, pos = _decode_v8(data, pos)
            v, pos = _decode_v8(data, pos)
            if isinstance(k, int):
                while len(arr) <= k:
                    arr.append(None)
                arr[k] = v
        return arr, pos
    return None, pos  # unknown tag — skip


def _find_v8_start(data: bytes) -> int:
    """Find the offset of the innermost V8 version marker (0xFF followed by small int)."""
    VALID_NEXT = {0x6F, 0x41, 0x61, 0x3F, 0x00, 0xFF, 0x22, 0x53, 0x63, 0x5F, 0x30}
    for i in range(len(data) - 2):
        if data[i] == 0xFF and data[i + 1] < 32 and data[i + 2] in VALID_NEXT:
            return i
    return -1


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
        console.print(f'[yellow]Could not read bookmarks for {profile_name!r}: {e}[/yellow]')
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

    safe = profile_name.replace(' ', '_').replace('/', '_')
    tmp_history = tmp_base / f'tmp_history_{safe}'

    try:
        shutil.copy2(history_path, tmp_history)
        # Copy journal/WAL files so SQLite sees a consistent snapshot
        for suffix in ('-journal', '-wal', '-shm'):
            src = history_path.parent / (history_path.name + suffix)
            if src.exists():
                shutil.copy2(src, tmp_history.parent / (tmp_history.name + suffix))
    except Exception as e:
        console.print(f'[bold red]Error copying History for {profile_name!r}:[/bold red] {e}')
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
        console.print(f'[bold red]Error reading History for {profile_name!r}:[/bold red] {e}')
    finally:
        for suffix in ('', '-journal', '-wal', '-shm'):
            p = tmp_history.parent / (tmp_history.name + suffix)
            if not keep_tmp and p.exists():
                p.unlink()

    return tabs


def extract_onetab_legacy(profile_dir: Path, profile_name: str,
                           tmp_base: Path, keep_tmp: bool) -> tuple[list[dict], bool]:
    """Extract OneTab data from legacy LevelDB (Local Extension Settings)."""
    db_path = profile_dir / 'Local Extension Settings' / ONETAB_EXTENSION_ID
    if not db_path.exists():
        return []

    safe = profile_name.replace(' ', '_').replace('/', '_')
    tmp_db = tmp_base / f'tmp_onetab_legacy_{safe}'
    try:
        if tmp_db.exists():
            shutil.rmtree(tmp_db)
        shutil.copytree(db_path, tmp_db)
    except Exception as e:
        console.print(f'[bold red]Error copying legacy OneTab for {profile_name!r}:[/bold red] {e}')
        return []

    tabs = []
    migrated = False
    try:
        db = plyvel.DB(str(tmp_db), create_if_missing=False)
        raw_state = db.get(b'state')
        migrated = db.get(b'stateMigratedToIDB') is not None
        db.close()

        if not migrated and raw_state:
            state_data = json.loads(json.loads(raw_state.decode('utf-8')))
            for group in state_data.get('tabGroups', []):
                label = group.get('label') or 'Untitled Group'
                date_str = ms_epoch_to_str(group.get('createDate'))
                color = group.get('color', '')
                group_type = group.get('groupType', '')
                group_label = f'{label} [{group_type}]' if group_type else label
                for tab in group.get('tabsMeta', []):
                    tabs.append({
                        'Profile': profile_name,
                        'Source': 'OneTab',
                        'Group': group_label,
                        'Date': date_str,
                        'Color': color,
                        'Title': tab.get('title', 'No Title'),
                        'URL': tab.get('url', ''),
                    })
    except Exception as e:
        console.print(f'[bold red]Error reading legacy OneTab for {profile_name!r}:[/bold red] {e}')
    finally:
        if not keep_tmp and tmp_db.exists():
            shutil.rmtree(tmp_db)

    return tabs, migrated


def extract_onetab_idb(profile_dir: Path, profile_name: str,
                        tmp_base: Path, keep_tmp: bool) -> list[dict]:
    """Extract OneTab data from IndexedDB (newer OneTab versions)."""
    idb_dir = (profile_dir / 'IndexedDB' /
               f'chrome-extension_{ONETAB_EXTENSION_ID}_0.indexeddb.leveldb')
    if not idb_dir.exists():
        return []

    safe = profile_name.replace(' ', '_').replace('/', '_')
    tmp_db = tmp_base / f'tmp_onetab_idb_{safe}'
    try:
        if tmp_db.exists():
            shutil.rmtree(tmp_db)
        shutil.copytree(idb_dir, tmp_db)
    except Exception as e:
        console.print(f'[bold red]Error copying OneTab IDB for {profile_name!r}:[/bold red] {e}')
        return []

    groups: dict[str, dict] = {}   # id -> group record
    tab_records: list[dict] = []

    try:
        def _bytewise(a, b): return (a > b) - (a < b)
        db = plyvel.DB(str(tmp_db), create_if_missing=False,
                       comparator=_bytewise, comparator_name=b'idb_cmp1')

        for _, raw in db:
            idx = _find_v8_start(raw)
            if idx == -1:
                continue
            try:
                obj, _ = _decode_v8(raw, idx)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            rec_type = obj.get('type')
            if rec_type == 'group':
                groups[obj['id']] = obj
            elif rec_type == 'tab':
                tab_records.append(obj)

        db.close()
    except Exception as e:
        console.print(f'[yellow]Could not read OneTab IDB for {profile_name!r}: {e}[/yellow]')
    finally:
        if not keep_tmp and tmp_db.exists():
            shutil.rmtree(tmp_db)

    tabs = []
    for tab in tab_records:
        url = tab.get('url', '')
        if not isinstance(url, str) or not url.startswith('http'):
            continue

        # Resolve group label from parentIds
        parent_ids = tab.get('parentIds') or []
        if not isinstance(parent_ids, list):
            parent_ids = []
        group_label = ''
        color = ''
        for pid in parent_ids:
            if isinstance(pid, str) and pid in groups:
                g = groups[pid]
                group_label = g.get('label') or g.get('groupType') or ''
                color = g.get('color', '')
                break

        tabs.append({
            'Profile': profile_name,
            'Source': 'OneTab',
            'Group': group_label or 'OneTab',
            'Date': ms_epoch_to_str(tab.get('createDate')),
            'Color': color,
            'Title': tab.get('title') or 'No Title',
            'URL': url,
        })

    return tabs


def extract_onetab(profile_dir: Path, profile_name: str,
                   tmp_base: Path, keep_tmp: bool) -> list[dict]:
    """Dispatcher: tries legacy LevelDB first; falls back to IDB if migrated."""
    result = extract_onetab_legacy(profile_dir, profile_name, tmp_base, keep_tmp)
    tabs, migrated = result if isinstance(result, tuple) else (result, False)

    if migrated or not tabs:
        idb_tabs = extract_onetab_idb(profile_dir, profile_name, tmp_base, keep_tmp)
        if idb_tabs:
            return idb_tabs
        elif migrated:
            console.print(f'[yellow]OneTab in {profile_name!r}: IDB found but no data decoded.[/yellow]')

    return tabs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    chrome_dir = get_chrome_dir()

    parser = argparse.ArgumentParser(
        description='Export Chrome bookmarks, history, and OneTab data to CSV.')

    parser.add_argument('--chrome-dir', type=str, default=str(chrome_dir),
                        help='Chrome user data directory')
    parser.add_argument('--all-profiles', action=argparse.BooleanOptionalAction, default=True,
                        help='Scan all profiles (default: on)')

    parser.add_argument('--bookmarks', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--history', action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument('--onetab', action=argparse.BooleanOptionalAction, default=True)

    parser.add_argument('-o', '--output', type=str)
    parser.add_argument('-d', '--dir', type=str,
                        default=os.getenv('OUTPUT_DIR') or None)
    parser.add_argument('-dr', '--dryrun', action='store_true')
    parser.add_argument('-p', '--print', action='store_true')
    parser.add_argument('--keep-tmp', action='store_true')

    args = parser.parse_args()

    project_dir = Path(args.dir).resolve() if args.dir else Path.cwd()
    resolved_chrome_dir = Path(args.chrome_dir).expanduser()

    if args.all_profiles:
        profiles = find_profiles(resolved_chrome_dir)
        if not profiles:
            console.print(f'[bold yellow]No Chrome profiles found under:[/bold yellow] {resolved_chrome_dir}')
            return
        console.print(f'Found [bold]{len(profiles)}[/bold] profile(s).')
    else:
        default_dir = resolved_chrome_dir / 'Default'
        profiles = [(default_dir, get_profile_identifier(default_dir))]

    all_rows = []

    for profile_dir, profile_name in profiles:
        if args.bookmarks:
            rows = extract_bookmarks(profile_dir, profile_name)
            if rows:
                console.print(f'  [dim]{profile_name}[/dim] bookmarks: [cyan]{len(rows)}[/cyan]')
            all_rows.extend(rows)

        if args.history:
            rows = extract_history(profile_dir, profile_name, project_dir, args.keep_tmp)
            if rows:
                console.print(f'  [dim]{profile_name}[/dim] history:   [cyan]{len(rows)}[/cyan]')
            all_rows.extend(rows)

        if args.onetab:
            rows = extract_onetab(profile_dir, profile_name, project_dir, args.keep_tmp)
            if rows:
                console.print(f'  [dim]{profile_name}[/dim] onetab:    [cyan]{len(rows)}[/cyan]')
            all_rows.extend(rows)

    # Sort most-recent-first; rows with no date sort to the end
    all_rows.sort(key=lambda r: r['Date'] or '0', reverse=True)

    if args.dryrun:
        source_counts: dict[str, int] = {}
        for row in all_rows:
            source_counts[row['Source']] = source_counts.get(row['Source'], 0) + 1
        breakdown = '  '.join(f'[bold]{s}[/bold]: {n}' for s, n in sorted(source_counts.items()))
        console.print(Panel(
            f'[bold cyan]{len(all_rows)}[/bold cyan] total rows across '
            f'{len(profiles)} profile(s)\n{breakdown}'))
        return

    date_str = datetime.now().strftime('%Y_%m_%d')
    filename = args.output if args.output else f'{date_str}_ChromeExport.csv'
    full_output_path = project_dir / filename

    with open(full_output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    console.print(
        f'\n[bold green]Success![/bold green] Exported [bold cyan]{len(all_rows)}[/bold cyan] rows '
        f'to [underline]{full_output_path}[/underline]')

    if args.print:
        table = Table(title='Chrome Export Preview', expand=False)
        table.add_column('Profile', style='white', max_width=15, overflow='fold')
        table.add_column('Source', style='blue', max_width=10)
        table.add_column('Group', style='magenta', max_width=18, overflow='fold')
        table.add_column('Date', style='yellow', max_width=19)
        table.add_column('Title', style='cyan', max_width=28, overflow='fold')
        table.add_column('URL', style='green', max_width=38, overflow='fold')

        for item in all_rows[:20]:
            table.add_row(item['Profile'], item['Source'], item['Group'],
                          item['Date'], item['Title'], item['URL'])

        console.print(table)
        if len(all_rows) > 20:
            console.print(f'... and {len(all_rows) - 20} more rows.')


if __name__ == '__main__':
    main()
