#!/usr/bin/env python3
"""
Gemling - Toggl to GEM Time Entry Utility

Transforms Toggl time tracking data into a cell-by-cell interactive guide
for entering into GEM, respecting daily/weekly hour constraints.

Features:
- Rounds hours up to 0.25h increments
- Shows weekly grid matching GEM's layout
- Guides you cell-by-cell with project, milestone, hours, and notes
- Handles splits with part numbers (pt.1/2, pt.2/2)
- Can mark entries as billed in Toggl after completion
"""

import argparse
import sys
from pathlib import Path

from rich.console import Console

from parser import parse_toggl_csv, parse_assignments
from scheduler import schedule_entries
from output import run_interactive_guide
from toggl_api import create_toggl_client


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Transform Toggl time entries into GEM entry instructions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s data/toggl_export.csv -a data/assignments.yml
  %(prog)s export.csv --max-daily 7.5 --max-weekly 37.5
  %(prog)s export.csv -t YOUR_TOGGL_API_TOKEN

Assignments file format (YAML):
  assignments:
    "Toggl Project Name":
      project: "GEM Project Name"
      milestone: "GEM Milestone"
      color: "cyan"
"""
    )
    parser.add_argument(
        "csv_file",
        type=Path,
        help="Toggl CSV export file (Detailed report with all columns)"
    )
    parser.add_argument(
        "--assignments", "-a",
        type=Path,
        default=Path("assignments.yml"),
        help="YAML file mapping Toggl projects to GEM project/milestone (default: assignments.yml)"
    )
    parser.add_argument(
        "--toggl-token", "-t",
        type=str,
        default=None,
        help="Toggl API token to mark entries as billed after completion"
    )
    parser.add_argument(
        "--max-daily", "-d",
        type=float,
        default=8.0,
        help="Max hours per day (default: 8.0)"
    )
    parser.add_argument(
        "--max-weekly", "-w",
        type=float,
        default=40.0,
        help="Max hours per week (default: 40.0)"
    )

    args = parser.parse_args()
    console = Console()

    # Validate inputs
    if not args.csv_file.exists():
        console.print(f"[red]Error: CSV file not found: {args.csv_file}[/red]")
        return 1

    if not args.assignments.exists():
        console.print(f"[red]Error: Assignments file not found: {args.assignments}[/red]")
        return 1

    # Parse input files
    try:
        toggl_entries = parse_toggl_csv(str(args.csv_file))
        assignments = parse_assignments(str(args.assignments))
    except Exception as e:
        console.print(f"[red]Error parsing input files: {e}[/red]")
        return 1

    if not toggl_entries:
        console.print("[yellow]No entries found in CSV file.[/yellow]")
        return 0

    console.print(f"[dim]Loaded {len(toggl_entries)} entries from Toggl[/dim]")
    console.print(f"[dim]Using {len(assignments)} project mappings[/dim]")

    # Check for unmapped projects
    unmapped = set()
    for entry in toggl_entries:
        if entry.project not in assignments:
            unmapped.add(entry.project)

    if unmapped:
        console.print(f"[yellow]Warning: {len(unmapped)} unmapped projects:[/yellow]")
        for project in sorted(unmapped):
            console.print(f"[yellow]  - {project}[/yellow]")
        console.print()

    # Schedule entries
    gem_entries, original_total, scheduled_total = schedule_entries(
        toggl_entries,
        assignments,
        max_hours_per_day=args.max_daily,
        max_hours_per_week=args.max_weekly,
    )

    # Set up Toggl API callback if token provided
    mark_billed_callback = None
    if args.toggl_token:
        toggl_client = create_toggl_client(args.toggl_token)
        if toggl_client:
            def mark_billed():
                console.print("[dim]Marking entries as billed in Toggl...[/dim]")
                success, failed = toggl_client.mark_entries_as_billed(
                    toggl_entries,
                    lambda current, total: console.print(
                        f"[dim]Progress: {current}/{total}[/dim]",
                        end="\r"
                    )
                )
                console.print()
                if success > 0:
                    console.print(f"[green]Marked {success} entries as billed[/green]")
                if failed > 0:
                    console.print(f"[yellow]Failed to mark {failed} entries[/yellow]")

            mark_billed_callback = mark_billed
        else:
            console.print("[yellow]Warning: Could not connect to Toggl API[/yellow]")

    # Run interactive guide
    run_interactive_guide(
        gem_entries,
        original_total,
        scheduled_total,
        console,
        mark_billed_callback,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())
