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
                metadata_parts = []
                if group.get('starred'): metadata_parts.append("starred")
                if group.get('locked'): metadata_parts.append("locked")
                metadata = ", ".join(metadata_parts)

                extracted_data.append({
                    'Source': 'OneTab',
                    'Category/Group': label,
                    'Title': tab.get('title', 'No Title'),
                    'URL': tab.get('url', ''),
                    'Date Added': date_saved,
                    'Color': color,
                    'Metadata': metadata
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
    Extracts open tabs from Chrome's Sessions directory by parsing binary SNSS files.
    This is a cross-platform approach that doesn't rely on AppleScript.
    """
    extracted_data = []
    
    if not sessions_path.exists():
        console.print(f"[yellow]Sessions directory not found at {sessions_path}[/yellow]")
        return extracted_data

    def read_str(data: bytes, offset: int, is_utf16: bool = False):
        if offset + 4 > len(data): return None, offset
        length = int.from_bytes(data[offset:offset+4], 'little')
        offset += 4
        byte_len = length * (2 if is_utf16 else 1)
        if offset + byte_len > len(data): return None, offset
        try:
            encoding = 'utf-16' if is_utf16 else 'utf-8'
            s = data[offset:offset+byte_len].decode(encoding, errors='ignore')
        except:
            s = ""
        return s, offset + byte_len

    try:
        # Check both Session_* and Tabs_* files
        session_files = list(sessions_path.glob('Session_*')) + list(sessions_path.glob('Tabs_*'))
        # Sort by modification time to get the most recent data
        session_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        seen_urls = set()

        for snss_file in session_files[:3]: # Scan top 3 most recent files
            with open(snss_file, 'rb') as f:
                header = f.read(4)
                if header != b'SNSS':
                    continue
                f.read(4) # skip version
                
                while True:
                    size_buf = f.read(2)
                    if not size_buf:
                        break
                    size = int.from_bytes(size_buf, 'little')
                    if size == 0: continue
                    command_id = ord(f.read(1))
                    data = f.read(size - 1)
                    
                    # We look for http strings anywhere in the command data
                    # This is more robust than relying on specific command IDs which vary by Chrome version
                    idx = data.find(b'http')
                    while idx != -1:
                        # Attempt to see if this is a length-prefixed string
                        if idx >= 4:
                            length = int.from_bytes(data[idx-4:idx], 'little')
                            if length > 0 and length < 2048 and idx + length <= len(data):
                                try:
                                    url = data[idx:idx+length].decode('utf-8')
                                    if url.startswith('http') and url not in seen_urls:
                                        # Try to find a title. Usually titles follow URLs in these files.
                                        # We look for a UTF-16 string shortly after the URL.
                                        title = "Open Tab"
                                        search_offset = idx + length
                                        # Skip some bytes that might be referrer or other flags
                                        for offset in range(search_offset, min(search_offset + 100, len(data) - 4)):
                                            t_len = int.from_bytes(data[offset:offset+4], 'little')
                                            if 0 < t_len < 500:
                                                t_bytes = data[offset+4:offset+4+t_len*2]
                                                if len(t_bytes) == t_len * 2:
                                                    try:
                                                        t_str = t_bytes.decode('utf-16').strip()
                                                        if t_str and any(c.isalnum() for c in t_str):
                                                            title = t_str
                                                            break
                                                    except: pass
                                        
                                        seen_urls.add(url)
                                        extracted_data.append({
                                            'Source': 'Open Tab',
                                            'Category/Group': 'Current Session',
                                            'Title': title,
                                            'URL': url,
                                            'Date Added': datetime.fromtimestamp(snss_file.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
                                            'Color': 'green',
                                            'Metadata': f"file={snss_file.name}"
                                        })
                                except:
                                    pass
                        idx = data.find(b'http', idx + 1)

    except Exception as e:
        console.print(f"[yellow]Note: SNSS extraction limited:[/yellow] {e}")

    # Fallback if no tabs were found
    if not extracted_data:
        extracted_data.append({
            'Source': 'Open Tab',
            'Category/Group': 'Current Session',
            'Title': 'Chrome Session (Active)',
            'URL': 'chrome://history',
            'Date Added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Color': 'blue',
            'Metadata': 'snss_fallback'
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
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Extract History + Search Terms with more metadata
        # Transition types: 0=Link, 1=Typed, 2=Auto_Bookmark, 7=Reload, etc.
        TRANSITIONS = {
            0: "link", 1: "typed", 2: "auto_bookmark", 3: "auto_subframe", 
            4: "manual_subframe", 5: "generated", 6: "auto_toplevel", 
            7: "reload", 8: "keyword", 9: "keyword_generated"
        }

        query = f"""
        SELECT 
            u.url, u.title, u.last_visit_time, u.visit_count, u.typed_count,
            k.term as search_term,
            v.transition, v.is_known_to_sync
        FROM urls u
        LEFT JOIN keyword_search_terms k ON u.id = k.url_id
        JOIN visits v ON u.id = v.url  -- Note: v.url is the FK to urls.id in some versions
        WHERE u.hidden = 0
        GROUP BY u.id
        ORDER BY u.last_visit_time DESC
        LIMIT {limit}
        """
        cursor.execute(query)
        
        for row in cursor.fetchall():
            last_visit_raw = row['last_visit_time']
            date_added = ""
            if last_visit_raw:
                dt = datetime.fromtimestamp((last_visit_raw / 1000000) - 11644473600)
                date_added = dt.strftime('%Y-%m-%d %H:%M:%S')

            source = "History"
            title = row['title']
            if row['search_term']:
                source = "Search"
                title = f"Search: {row['search_term']}"

            # Comma-separated metadata
            metadata_parts = []
            trans_id = row['transition'] & 0xFF # Mask out core transition
            metadata_parts.append(f"trans={TRANSITIONS.get(trans_id, trans_id)}")
            if row['is_known_to_sync']:
                metadata_parts.append("synced")
            if row['visit_count'] > 1:
                metadata_parts.append(f"visits={row['visit_count']}")
            if row['typed_count'] > 0:
                metadata_parts.append(f"typed={row['typed_count']}")
            
            metadata = ", ".join(metadata_parts)

            extracted_data.append({
                'Source': source,
                'Category/Group': 'Browsing History',
                'Title': title or 'No Title',
                'URL': row['url'],
                'Date Added': date_added,
                'Color': 'grey70' if source == "History" else 'orange1',
                'Metadata': metadata
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
