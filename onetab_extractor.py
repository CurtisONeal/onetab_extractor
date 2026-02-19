#!/usr/bin/env -S uv run --quiet
# /// script
# dependencies = [
#   "plyvel-ci",
#   "rich",
# ]
# requires-python = ">=3.12"
# ///

import plyvel
import json
import csv
import shutil
import sqlite3
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from typing import List, Dict, Any, Optional

console = Console()

# Default Paths
CHROME_BASE = Path('~/Library/Application Support/Google/Chrome/Default').expanduser()
DEFAULT_ONETAB_PATH = CHROME_BASE / 'Local Extension Settings/chphlpgkkbolifaimnlloiipkdnihall'
DEFAULT_BOOKMARKS_PATH = CHROME_BASE / 'Bookmarks'
DEFAULT_SESSIONS_PATH = CHROME_BASE / 'Sessions'
DEFAULT_HISTORY_PATH = CHROME_BASE / 'History'

# Unified CSV structure columns
FIELDNAMES = ['Source', 'Category/Group', 'Title', 'URL', 'Date Added', 'Color', 'Metadata']

def extract_onetab(db_path: Path, tmp_dir: Path) -> List[Dict[str, Any]]:
    """Extracts data from OneTab LevelDB."""
    extracted_data = []
    if not db_path.exists():
        console.print(f"[yellow]OneTab database not found at {db_path}[/yellow]")
        return extracted_data

    tmp_db_path = tmp_dir / 'tmp_onetab_db'
    try:
        if tmp_db_path.exists():
            shutil.rmtree(tmp_db_path)
        shutil.copytree(db_path, tmp_db_path)
        
        db = plyvel.DB(str(tmp_db_path), create_if_missing=False)
        raw_state = db.get(b'state')
        if not raw_state:
            return extracted_data

        state_data = json.loads(json.loads(raw_state.decode('utf-8')))
        for group in state_data.get('tabGroups', []):
            label = group.get('label') or "Untitled Group"
            create_date = group.get('createDate')
            date_saved = datetime.fromtimestamp(create_date / 1000).strftime('%Y-%m-%d %H:%M:%S') if create_date else ''
            
            color = group.get('color', '')

            for tab in group.get('tabsMeta', []):
                extracted_data.append({
                    'Source': 'OneTab',
                    'Category/Group': label,
                    'Title': tab.get('title', 'No Title'),
                    'URL': tab.get('url', ''),
                    'Date Added': date_saved,
                    'Color': color,
                    'Metadata': ''
                })
        db.close()
    except Exception as e:
        console.print(f"[bold red]Error extracting OneTab:[/bold red] {e}")
    finally:
        if tmp_db_path.exists():
            shutil.rmtree(tmp_db_path)
            
    return extracted_data

def extract_bookmarks(bookmarks_path: Path) -> List[Dict[str, Any]]:
    """Extracts data from Chrome Bookmarks JSON file."""
    extracted_data = []
    if not bookmarks_path.exists():
        console.print(f"[yellow]Bookmarks file not found at {bookmarks_path}[/yellow]")
        return extracted_data

    try:
        with open(bookmarks_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        def parse_node(node: Dict[str, Any], path: str = ""):
            name = node.get('name', '')
            current_path = f"{path}/{name}" if path else name
            
            if node.get('type') == 'folder':
                for child in node.get('children', []):
                    parse_node(child, current_path)
            elif node.get('type') == 'url':
                # Chrome uses microseconds since 1601-01-01 for dates
                date_added_raw = int(node.get('date_added', 0))
                date_added = ""
                if date_added_raw:
                    # Approximation: subtract 11644473600 (seconds from 1601 to 1970)
                    dt = datetime.fromtimestamp((date_added_raw / 1000000) - 11644473600)
                    date_added = dt.strftime('%Y-%m-%d %H:%M:%S')

                extracted_data.append({
                    'Source': 'Bookmark',
                    'Category/Group': path,
                    'Title': node.get('name', 'No Title'),
                    'URL': node.get('url', ''),
                    'Date Added': date_added,
                    'Color': '',
                    'Metadata': ''
                })

        roots = data.get('roots', {})
        for root_key in ['bookmark_bar', 'other', 'synced']:
            if root_key in roots:
                parse_node(roots[root_key], root_key)

    except Exception as e:
        console.print(f"[bold red]Error extracting Bookmarks:[/bold red] {e}")

    return extracted_data

def extract_open_tabs(sessions_path: Path) -> List[Dict[str, Any]]:
    """
    Extracts open tabs from Chrome's Sessions directory.
    Note: SNSS format is complex; currently provides a detailed placeholder.
    """
    extracted_data = []
    
    # Try AppleScript first on macOS to get real-time open tabs across all windows
    try:
        applescript = """
        tell application "Google Chrome"
            set resultList to {}
            set theWindows to windows
            repeat with theWindow in theWindows
                set theTabs to tabs of theWindow
                repeat with theTab in theTabs
                    set end of resultList to (title of theTab & "|||" & URL of theTab)
                end repeat
            end repeat
            return resultList
        end tell
        """
        process = subprocess.run(['osascript', '-e', applescript], capture_output=True, text=True)
        if process.returncode == 0:
            output = process.stdout.strip()
            if output:
                tabs = output.split(', ')
                for tab_str in tabs:
                    if '|||' in tab_str:
                        title, url = tab_str.split('|||', 1)
                        extracted_data.append({
                            'Source': 'Open Tab',
                            'Category/Group': 'Active Window',
                            'Title': title.strip(),
                            'URL': url.strip(),
                            'Date Added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'Color': 'green',
                            'Metadata': ''
                        })
                return extracted_data
    except Exception:
        pass # Fallback to placeholder if AppleScript fails

    # Placeholder for non-macOS or if AppleScript fails
    extracted_data.append({
        'Source': 'Open Tab',
        'Category/Group': 'Current Session',
        'Title': 'Chrome Session (Placeholder)',
        'URL': 'chrome://history',
        'Date Added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'Color': 'blue',
        'Metadata': 'SNSS parser pending'
    })
    
    return extracted_data

def extract_history(history_path: Path, tmp_dir: Path, limit: int = 500) -> List[Dict[str, Any]]:
    """Extracts browsing history and search terms from Chrome SQLite database."""
    extracted_data = []
    if not history_path.exists():
        console.print(f"[yellow]History database not found at {history_path}[/yellow]")
        return extracted_data

    tmp_history_path = tmp_dir / 'tmp_history'
    try:
        shutil.copy2(history_path, tmp_history_path)
        conn = sqlite3.connect(str(tmp_history_path))
        cursor = conn.cursor()

        # Extract History + Search Terms
        query = f"""
        SELECT 
            u.url, u.title, u.last_visit_time, k.term
        FROM urls u
        LEFT JOIN keyword_search_terms k ON u.id = k.url_id
        WHERE u.hidden = 0
        ORDER BY u.last_visit_time DESC
        LIMIT {limit}
        """
        cursor.execute(query)
        
        for url, title, last_visit_raw, search_term in cursor.fetchall():
            # Chrome uses microseconds since 1601-01-01
            date_added = ""
            if last_visit_raw:
                dt = datetime.fromtimestamp((last_visit_raw / 1000000) - 11644473600)
                date_added = dt.strftime('%Y-%m-%d %H:%M:%S')

            source = "History"
            if search_term:
                source = "Search"
                title = f"Search: {search_term}"

            extracted_data.append({
                'Source': source,
                'Category/Group': 'Browsing History',
                'Title': title or 'No Title',
                'URL': url,
                'Date Added': date_added,
                'Color': 'grey70' if source == "History" else 'orange1',
                'Metadata': ''
            })
            
        conn.close()
    except Exception as e:
        console.print(f"[bold red]Error extracting History:[/bold red] {e}")
    finally:
        if tmp_history_path.exists():
            tmp_history_path.unlink()

    return extracted_data

def write_unified_csv(data: List[Dict[str, Any]], output_path: Path):
    """Writes the unified data to a CSV file."""
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()
            writer.writerows(data)
        console.print(f"[bold green]Success![/bold green] Exported to [underline]{output_path}[/underline]")
    except Exception as e:
        console.print(f"[bold red]Error writing CSV:[/bold red] {e}")

def main():
    parser = argparse.ArgumentParser(description='Extract Unified Browser Data (OneTab, Bookmarks, Open Tabs).')

    # Path configuration
    parser.add_argument('--onetab-path', type=str, default=str(DEFAULT_ONETAB_PATH), help='OneTab LevelDB path')
    parser.add_argument('--bookmarks-path', type=str, default=str(DEFAULT_BOOKMARKS_PATH), help='Chrome Bookmarks path')
    parser.add_argument('--sessions-path', type=str, default=str(DEFAULT_SESSIONS_PATH), help='Chrome Sessions path')
    parser.add_argument('--history-path', type=str, default=str(DEFAULT_HISTORY_PATH), help='Chrome History path')

    # Output configuration
    parser.add_argument('-o', '--output', type=str, help='CSV filename')
    parser.add_argument('-d', '--dir', type=str, help='Output directory')
    parser.add_argument('--history-limit', type=int, default=500, help='Limit the number of history items to extract')

    # Flags
    parser.add_argument('-dr', '--dryrun', action='store_true', help='Count rows without exporting')
    parser.add_argument('-p', '--print', action='store_true', help='Pretty print the results to terminal')

    args = parser.parse_args()

    # Resolve paths
    onetab_path = Path(args.onetab_path).expanduser()
    bookmarks_path = Path(args.bookmarks_path).expanduser()
    sessions_path = Path(args.sessions_path).expanduser()
    history_path = Path(args.history_path).expanduser()
    
    project_dir = Path(args.dir).resolve() if args.dir else Path.cwd()
    
    # 1. Extraction
    all_data = []
    
    all_data.extend(extract_open_tabs(sessions_path))
    all_data.extend(extract_bookmarks(bookmarks_path))
    all_data.extend(extract_onetab(onetab_path, project_dir))
    all_data.extend(extract_history(history_path, project_dir, args.history_limit))

    # 2. Output Handling
    date_str = datetime.now().strftime('%Y_%m_%d')
    filename = args.output if args.output else f"{date_str}_UnifiedBrowserData.csv"
    full_output_path = project_dir / filename

    if args.dryrun:
        sources = {}
        for item in all_data:
            sources[item['Source']] = sources.get(item['Source'], 0) + 1
        
        summary = ", ".join([f"[bold cyan]{count}[/bold cyan] {src}" for src, count in sources.items()])
        console.print(Panel(f"Found {summary} items."))

    if not args.dryrun:
        write_unified_csv(all_data, full_output_path)

    if args.print:
        table = Table(title="Unified Browser Data Preview", expand=True)
        for field in FIELDNAMES:
            table.add_column(field, overflow="fold")

        for item in all_data[:30]:  # Preview first 30
            table.add_row(*[str(item.get(f, "")) for f in FIELDNAMES])

        console.print(table)
        if len(all_data) > 30:
            console.print(f"... and {len(all_data) - 30} more rows.")

if __name__ == "__main__":
    main()
