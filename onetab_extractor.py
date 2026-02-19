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
import argparse
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()
# Default path for OneTab LevelDB (macOS)
DEFAULT_ONETAB_PATH = Path('~/Library/Application Support/Google/Chrome/Default/Local Extension Settings/chphlpgkkbolifaimnlloiipkdnihall').expanduser()

def main():
    parser = argparse.ArgumentParser(description='Extract OneTab links via uv.')

    # Path configuration
    parser.add_argument('--path', type=str,
                        default=str(DEFAULT_ONETAB_PATH),
                        help='Source OneTab LevelDB path')

    # Output configuration
    parser.add_argument('-o', '--output', type=str, help='CSV filename')
    parser.add_argument('-d', '--dir', type=str, help='Output directory (defaults to current working directory)')

    # Flags
    parser.add_argument('-dr', '--dryrun', action='store_true', help='Count rows without exporting')
    parser.add_argument('-p', '--print', action='store_true', help='Pretty print the results to terminal')
    parser.add_argument('--keep-tmp', action='store_true', help='Do not delete the temporary database copy')

    args = parser.parse_args()

    # Resolve paths
    src_db_path = Path(args.path).expanduser()
    # Use CWD for output if no directory specified via args
    project_dir = Path(args.dir).resolve() if args.dir else Path.cwd()
    tmp_db_path = project_dir / 'tmp_onetab_db'

    # 1. Live Copy Feature
    try:
        if tmp_db_path.exists():
            shutil.rmtree(tmp_db_path)
        shutil.copytree(src_db_path, tmp_db_path)
    except Exception as e:
        console.print(f"[bold red]Error copying database:[/bold red] {e}")
        return

    # Default filename logic
    date_str = datetime.now().strftime('%Y_%m_%d')
    filename = args.output if args.output else f"{date_str}_OneTabOutput.csv"
    full_output_path = project_dir / filename

    try:
        # 2. Extraction Logic
        db = plyvel.DB(str(tmp_db_path), create_if_missing=False)
        raw_state = db.get(b'state')

        if not raw_state:
            console.print("[bold yellow]No 'state' key found. OneTab might be empty or path is wrong.[/bold yellow]")
            return

        state_data = json.loads(json.loads(raw_state.decode('utf-8')))

        tabs_to_export = []
        for group in state_data.get('tabGroups', []):
            label = group.get('label') or "Untitled Group"
            create_date = group.get('createDate')
            # Convert milliseconds timestamp to readable date
            date_saved = datetime.fromtimestamp(create_date / 1000).strftime('%Y-%m-%d %H:%M:%S') if create_date else ''
            color = group.get('color', '')
            group_type = group.get('groupType', '')

            for tab in group.get('tabsMeta', []):
                tabs_to_export.append({
                    'Group': label,
                    'Date Saved': date_saved,
                    'Color': color,
                    'Group Type': group_type,
                    'Title': tab.get('title', 'No Title'),
                    'URL': tab.get('url', '')
                })

        # 3. Handle Flags
        if args.dryrun:
            console.print(Panel(
                f"Found [bold cyan]{len(tabs_to_export)}[/bold cyan] tabs across {len(state_data.get('tabGroups', []))} groups."))

        if not args.dryrun:
            with open(full_output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=['Group', 'Date Saved', 'Color', 'Group Type', 'Title', 'URL'])
                writer.writeheader()
                writer.writerows(tabs_to_export)
            console.print(f"[bold green]Success![/bold green] Exported to [underline]{full_output_path}[/underline]")

        if args.print:
            table = Table(title="OneTab Extraction Preview", expand=False)
            table.add_column("Group", style="magenta", max_width=20, overflow="fold")
            table.add_column("Date Saved", style="yellow", max_width=19)
            table.add_column("Color", style="blue", max_width=10)
            table.add_column("Title", style="cyan", max_width=30, overflow="fold")
            table.add_column("URL", style="green", max_width=40, overflow="fold")

            for item in tabs_to_export[:20]:  # Preview first 20
                table.add_row(item['Group'], item['Date Saved'], item['Color'], item['Title'], item['URL'])

            console.print(table)
            if len(tabs_to_export) > 20:
                console.print(f"... and {len(tabs_to_export) - 20} more rows.")

        db.close()

    except Exception as e:
        console.print(f"[bold red]An error occurred:[/bold red] {e}")
    finally:
        # 4. Clean up the temp directory
        if not args.keep_tmp and tmp_db_path.exists():
            shutil.rmtree(tmp_db_path)


if __name__ == "__main__":
    main()
