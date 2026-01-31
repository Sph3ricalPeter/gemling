"""Interactive step-by-step guide output."""

import sys
from collections import defaultdict
from datetime import date, timedelta
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from scheduler import GemEntry, get_week_number, get_nearest_working_day


def wait_for_keypress(console: Console) -> bool:
    """Wait for Enter or Space to continue. Returns False if user wants to quit (Ctrl+C, q)."""
    console.print("[dim]Press Space or Enter to continue (q to quit)...[/dim]", end="")

    try:
        if sys.platform == "win32":
            import msvcrt
            while True:
                if msvcrt.kbhit():
                    key = msvcrt.getch()
                    # Space (0x20), Enter (0x0d), or 'q'
                    if key in (b' ', b'\r', b'\n'):
                        console.print()  # newline
                        return True
                    elif key in (b'q', b'Q'):
                        console.print()
                        return False
        else:
            # Unix-like systems
            import tty
            import termios
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                key = sys.stdin.read(1)
                if key in (' ', '\r', '\n'):
                    console.print()
                    return True
                elif key in ('q', 'Q', '\x03'):  # \x03 is Ctrl+C
                    console.print()
                    return False
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except (KeyboardInterrupt, EOFError):
        console.print()
        return False

    return True




def format_date(d: date) -> str:
    """Format date as 'Weekday, YYYY-MM-DD'."""
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    return f"{weekdays[d.weekday()]}, {d.strftime('%Y-%m-%d')}"


def print_summary(
    gem_entries: list[GemEntry],
    original_total: float,
    scheduled_total: float,
    console: Console,
) -> None:
    """Print summary of hours to be entered."""
    diff = scheduled_total - original_total
    diff_str = f"+{diff:.2f}" if diff >= 0 else f"{diff:.2f}"

    console.print()
    console.print(Panel.fit(
        f"[bold]Toggl total:[/bold] {original_total:.2f}h\n"
        f"[bold]GEM total:[/bold]   {scheduled_total:.2f}h ({diff_str}h after rounding)\n"
        f"[bold]Entries:[/bold]     {len(gem_entries)}",
        title="[bold cyan]=== GEM Time Entry Guide ===[/bold cyan]",
        border_style="cyan"
    ))

    # Show assignment breakdown with colors
    # Key: assignment -> {hours, color}
    assignment_totals: dict[str, dict] = {}
    for entry in gem_entries:
        if entry.gem_assignment not in assignment_totals:
            assignment_totals[entry.gem_assignment] = {"hours": 0.0, "color": entry.color}
        assignment_totals[entry.gem_assignment]["hours"] += entry.hours

    if assignment_totals:
        console.print()
        console.print("[bold]Projects:[/bold]")
        for assignment, info in sorted(assignment_totals.items(), key=lambda x: -x[1]["hours"]):
            line = Text("  ")
            line.append(assignment, style=info["color"])
            line.append(f": {info['hours']:.2f}h")
            console.print(line)

    # Show description breakdown with assignment, project, and entry count
    # Key: (description, project) -> {hours, assignment, count, color, dates, original_entries, gem_entries}
    description_info: dict[tuple[str, str], dict] = {}
    for entry in gem_entries:
        key = (entry.description, entry.toggl_project)
        if key not in description_info:
            description_info[key] = {
                "hours": 0.0,
                "assignment": entry.gem_assignment,
                "count": 0,
                "color": entry.color,
                "dates": set(),
                "original_entries": [],
                "gem_entries": [],
            }
        description_info[key]["hours"] += entry.hours
        description_info[key]["count"] += entry.entry_count
        description_info[key]["dates"].update(entry.original_dates)
        # Collect all original entries (allow multiple per date)
        description_info[key]["original_entries"].extend(entry.original_entries)
        description_info[key]["gem_entries"].append(entry)

    if description_info:
        console.print()
        console.print("[bold]Descriptions:[/bold]")

        # Rainbow colors for IDs
        rainbow = ["red", "yellow", "green", "cyan", "blue", "magenta",
                   "bright_red", "bright_yellow", "bright_green", "bright_cyan", "bright_blue", "bright_magenta"]

        from rich.table import Table as RichTable
        desc_table = RichTable(box=None, show_header=True, padding=(0, 1))
        desc_table.add_column("#", justify="right")
        desc_table.add_column("Toggl Project")
        desc_table.add_column("GEM Project / Milestone")
        desc_table.add_column("Description", style="dim")
        desc_table.add_column("Total", justify="right")
        desc_table.add_column("GEM Output")
        desc_table.add_column("From", style="dim")
        desc_table.add_column("Ops", style="yellow")

        # Store idx->color mapping for week distribution
        idx_to_rainbow = {}

        for idx, ((desc, project), info) in enumerate(sorted(description_info.items(), key=lambda x: -x[1]["hours"]), 1):
            color = info["color"]
            display_desc = desc if len(desc) <= 30 else desc[:27] + "..."
            row_color = rainbow[(idx - 1) % len(rainbow)]
            idx_to_rainbow[idx] = row_color

            # Compact GEM output
            gem_list = sorted(info["gem_entries"], key=lambda g: g.target_date)
            gem_parts = [f"{g.target_date.strftime('%m/%d')} {g.hours:.2f}h" for g in gem_list]

            # Original date range
            orig_dates = sorted(info["dates"])
            orig_range = ""
            if orig_dates:
                orig_range = orig_dates[0].strftime('%m/%d')
                if len(orig_dates) > 1:
                    orig_range += f"-{orig_dates[-1].strftime('%m/%d')}"

            # Calculate operations (split, shift, round)
            ops = []

            # Check for rounding
            orig_entries = info["original_entries"]
            total_raw = sum(e.raw_hours for e in orig_entries)
            total_rounded = sum(e.rounded_hours for e in orig_entries)
            if total_rounded > total_raw + 0.01:
                ops.append(f"+{total_rounded - total_raw:.2f}h")

            # Check for split (multiple GEM entries from single description)
            if len(gem_list) > 1:
                ops.append("split")

            # Check for shift
            gem_dates = sorted(set(g.target_date for g in gem_list))
            if orig_dates and gem_dates:
                first_orig = get_nearest_working_day(orig_dates[0])
                first_gem = gem_dates[0]
                shift_days = (first_gem - first_orig).days
                if shift_days != 0:
                    ops.append(f"{'+' if shift_days > 0 else ''}{shift_days}d")

            desc_table.add_row(
                Text(f"{idx:02d}", style=f"bold {row_color}"),
                Text(project, style=color),
                Text(info["assignment"], style=color),
                display_desc,
                f"{info['hours']:.2f}h",
                " | ".join(gem_parts),
                orig_range,
                " ".join(ops) if ops else "-"
            )

        console.print(desc_table)

        # Build week visualization showing hours per day
        console.print()
        console.print("[bold]Week Distribution:[/bold]")

        # Map description to index
        desc_to_idx = {}
        for idx, ((desc, project), info) in enumerate(sorted(description_info.items(), key=lambda x: -x[1]["hours"]), 1):
            desc_to_idx[(desc, project)] = idx

        # Collect IDs and hours per day
        day_data: dict[date, dict[int, float]] = defaultdict(lambda: defaultdict(float))
        for entry in gem_entries:
            idx = desc_to_idx.get((entry.description, entry.toggl_project), 0)
            day_data[entry.target_date][idx] += entry.hours

        # Group days by week
        weeks: dict[tuple[int, int], list[date]] = defaultdict(list)
        for d in day_data.keys():
            weeks[get_week_number(d)].append(d)

        # Display header
        console.print("[dim]     Mon  Tue  Wed  Thu  Fri   Total  IDs[/dim]")

        bar_width = 4  # characters per day

        for week_key in sorted(weeks.keys()):
            year, week_num = week_key
            week_dates = sorted(weeks[week_key])
            week_start = week_dates[0] - timedelta(days=week_dates[0].weekday())

            line = Text()
            line.append(f"W{week_num:02d}  ", style="dim")

            week_total = 0.0
            week_ids = set()

            for day_offset in range(5):  # Mon-Fri
                day = week_start + timedelta(days=day_offset)
                day_hours = day_data.get(day, {})
                day_total = sum(day_hours.values())
                week_total += day_total
                week_ids.update(day_hours.keys())

                # Build mini bar
                fill = min(int((day_total / 8.0) * bar_width), bar_width)
                empty = bar_width - fill

                if day_total > 8:
                    style = "bold red"
                elif day_total >= 7.5:
                    style = "green"
                elif day_total > 0:
                    style = "cyan"
                else:
                    style = "dim"

                line.append("█" * fill, style=style)
                line.append("░" * empty, style="dim")
                line.append(" ", style="dim")

            # Week total
            total_style = "bold green" if week_total == 40 else "bold red" if week_total > 40 else "white"
            line.append(f" {week_total:5.2f}h ", style=total_style)

            # IDs in this week (colored)
            for i, idx in enumerate(sorted(week_ids)):
                if i > 0:
                    line.append(",", style="dim")
                id_color = idx_to_rainbow.get(idx, "white")
                line.append(f"{idx:02d}", style=id_color)

            console.print(line)

        console.print()


def print_day_summary(day_total: float, week_total: float, console: Console) -> None:
    """Print day and week totals."""
    console.print()
    console.print(f"[dim]Day total: {day_total:.2f}h | Week total: {week_total:.2f}h[/dim]")
    console.print()


def get_week_start(d: date) -> date:
    """Get Monday of the week containing date d."""
    return d - timedelta(days=d.weekday())


def print_weekly_grid(
    gem_entries: list[GemEntry],
    console: Console,
) -> None:
    """Print entries in a weekly grid format matching GEM's layout."""
    if not gem_entries:
        return

    # Group entries by week and assignment
    # week_data[week_start][assignment] = {date: hours, color: str, descriptions: set}
    week_data: dict[date, dict[str, dict]] = defaultdict(lambda: defaultdict(lambda: {
        "days": defaultdict(float),
        "color": "white",
        "descriptions": set(),
    }))

    for entry in gem_entries:
        week_start = get_week_start(entry.target_date)
        assignment = entry.gem_assignment
        week_data[week_start][assignment]["days"][entry.target_date] += entry.hours
        week_data[week_start][assignment]["color"] = entry.color
        if entry.description:
            week_data[week_start][assignment]["descriptions"].add(entry.description)

    # Print each week
    for week_start in sorted(week_data.keys()):
        week_num = get_week_number(week_start)
        week_end = week_start + timedelta(days=4)  # Friday

        console.print()
        console.print(Panel.fit(
            f"[bold]Week {week_num[1]} ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')})[/bold]",
            border_style="blue"
        ))

        # Build the table
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("Project / Assignment", style="bold", min_width=30)

        # Add day columns (Mon-Fri)
        weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri"]
        day_dates = [week_start + timedelta(days=i) for i in range(5)]
        for i, (day_name, day_date) in enumerate(zip(weekdays, day_dates)):
            table.add_column(f"{day_name}\n{day_date.strftime('%m/%d')}", justify="right", min_width=6)

        table.add_column("Total", justify="right", style="bold", min_width=6)

        # Track daily totals
        daily_totals = [0.0] * 5
        week_total = 0.0

        # Add rows for each assignment
        assignments = week_data[week_start]
        for assignment in sorted(assignments.keys()):
            info = assignments[assignment]
            color = info["color"]

            row = [Text(assignment, style=color)]
            row_total = 0.0

            for i, day_date in enumerate(day_dates):
                hours = info["days"].get(day_date, 0.0)
                if hours > 0:
                    row.append(Text(f"{hours:.2f}", style=color))
                    daily_totals[i] += hours
                    row_total += hours
                else:
                    row.append(Text("-", style="dim"))

            week_total += row_total
            row.append(Text(f"{row_total:.2f}", style=f"bold {color}"))
            table.add_row(*row)

            # Show descriptions under assignment if any
            if info["descriptions"]:
                descs = sorted(info["descriptions"])
                for desc in descs[:3]:  # Limit to 3 descriptions
                    display_desc = desc if len(desc) <= 40 else desc[:37] + "..."
                    desc_row = [Text(f"  {display_desc}", style="dim")]
                    desc_row.extend([""] * 6)  # Empty cells for days + total
                    table.add_row(*desc_row)

        # Add totals row
        table.add_row()  # Empty row for spacing
        totals_row = [Text("TOTAL", style="bold")]
        for i, total in enumerate(daily_totals):
            style = "bold green" if total == 8.0 else "bold yellow" if total > 8.0 else "bold"
            totals_row.append(Text(f"{total:.2f}", style=style))
        totals_row.append(Text(f"{week_total:.2f}", style="bold green" if week_total <= 40 else "bold yellow"))
        table.add_row(*totals_row)

        console.print(table)
        console.print()


def build_week_table(
    assignment_data: dict[str, dict],
    day_dates: list[date],
    current_assignment: Optional[str] = None,
    current_day: Optional[date] = None,
) -> tuple[Table, list[float], float]:
    """Build a weekly grid table, optionally highlighting current cell."""
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri"]

    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("Project / Assignment", style="bold", min_width=30)

    for day_name, day_date in zip(weekdays, day_dates):
        table.add_column(f"{day_name}\n{day_date.strftime('%m/%d')}", justify="right", min_width=6)

    table.add_column("Total", justify="right", style="bold", min_width=6)

    daily_totals = [0.0] * 5
    week_total = 0.0

    for assignment in sorted(assignment_data.keys()):
        info = assignment_data[assignment]
        color = info["color"]
        is_current_row = (assignment == current_assignment)

        # Assignment name - highlight if current row
        if is_current_row:
            row = [Text(f"> {assignment}", style=f"bold {color}")]
        else:
            row = [Text(assignment, style=color)]

        row_total = 0.0

        for i, day_date in enumerate(day_dates):
            hours = info["days"].get(day_date, 0.0)
            is_current_cell = (assignment == current_assignment and day_date == current_day)

            if hours > 0:
                if is_current_cell:
                    # Highlight current cell
                    row.append(Text(f"[{hours:.2f}]", style="bold reverse"))
                else:
                    row.append(Text(f"{hours:.2f}", style=color))
                daily_totals[i] += hours
                row_total += hours
            else:
                row.append(Text("-", style="dim"))

        week_total += row_total
        row.append(Text(f"{row_total:.2f}", style=f"bold {color}"))
        table.add_row(*row)

    # Totals row
    table.add_row()
    totals_row = [Text("TOTAL", style="bold")]
    for total in daily_totals:
        style = "bold green" if total == 8.0 else "bold yellow" if total > 8.0 else "bold"
        totals_row.append(Text(f"{total:.2f}", style=style))
    totals_row.append(Text(f"{week_total:.2f}", style="bold green" if week_total <= 40 else "bold yellow"))
    table.add_row(*totals_row)

    return table, daily_totals, week_total


def run_interactive_guide(
    gem_entries: list[GemEntry],
    original_total: float,
    scheduled_total: float,
    console: Optional[Console] = None,
    mark_billed_callback: Optional[callable] = None,
) -> None:
    """Run the interactive guide with cell-by-cell navigation."""
    if console is None:
        console = Console()

    print_summary(gem_entries, original_total, scheduled_total, console)

    if not gem_entries:
        console.print("[yellow]No entries to process.[/yellow]")
        return

    # Group entries by week
    weeks: dict[date, list[GemEntry]] = defaultdict(list)
    for entry in gem_entries:
        week_start = get_week_start(entry.target_date)
        weeks[week_start].append(entry)

    week_list = sorted(weeks.keys())
    total_weeks = len(week_list)
    cell_num = 0

    # Count total cells
    total_cells = 0
    for week_start in week_list:
        week_entries = weeks[week_start]
        day_dates = [week_start + timedelta(days=i) for i in range(5)]
        assignment_data: dict[str, dict] = defaultdict(lambda: {"days": defaultdict(float), "color": "white", "descriptions": defaultdict(set)})
        for entry in week_entries:
            assignment_data[entry.gem_assignment]["days"][entry.target_date] += entry.hours
        for assignment in assignment_data:
            for day_date in day_dates:
                if assignment_data[assignment]["days"].get(day_date, 0) > 0:
                    total_cells += 1

    for week_idx, week_start in enumerate(week_list, 1):
        week_entries = weeks[week_start]
        week_num = get_week_number(week_start)
        week_end = week_start + timedelta(days=4)
        day_dates = [week_start + timedelta(days=i) for i in range(5)]

        # Build assignment data with descriptions per cell
        # assignment -> {days: {date: hours}, color: str, descriptions: {date: set of descriptions}}
        assignment_data: dict[str, dict] = defaultdict(lambda: {
            "days": defaultdict(float),
            "color": "white",
            "descriptions": defaultdict(set),
        })

        for entry in week_entries:
            assignment_data[entry.gem_assignment]["days"][entry.target_date] += entry.hours
            assignment_data[entry.gem_assignment]["color"] = entry.color
            if entry.description:
                assignment_data[entry.gem_assignment]["descriptions"][entry.target_date].add(entry.description)

        # Build list of cells to iterate (assignment, day) pairs with hours > 0
        cells = []
        for assignment in sorted(assignment_data.keys()):
            for day_date in day_dates:
                if assignment_data[assignment]["days"].get(day_date, 0) > 0:
                    cells.append((assignment, day_date))

        # Iterate through each cell
        for cell_idx, (assignment, day_date) in enumerate(cells):
            cell_num += 1
            hours = assignment_data[assignment]["days"][day_date]
            descriptions = assignment_data[assignment]["descriptions"].get(day_date, set())
            color = assignment_data[assignment]["color"]
            day_name = ["Mon", "Tue", "Wed", "Thu", "Fri"][day_date.weekday()]

            console.print()
            console.print(Panel.fit(
                f"[bold]Week {week_idx}/{total_weeks}: Week {week_num[1]} ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d')})[/bold]",
                border_style="blue"
            ))

            # Build and show table with current cell highlighted
            table, _, _ = build_week_table(assignment_data, day_dates, assignment, day_date)
            console.print(table)

            # Show current cell info below the table
            # Find all entries that contributed to this cell
            current_entries = [e for e in week_entries
                               if e.gem_assignment == assignment and e.target_date == day_date]
            gem_project = current_entries[0].gem_project if current_entries else assignment
            gem_milestone = current_entries[0].gem_milestone if current_entries else ""

            console.print()
            console.print(f"[bold yellow][{cell_num}/{total_cells}][/bold yellow] {day_name} {day_date.strftime('%m/%d')}")
            console.print(f"[bold]Project:[/bold] ", end="")
            console.print(Text(gem_project, style=f"bold {color}"))
            if gem_milestone:
                console.print(f"[bold]Milestone:[/bold] ", end="")
                console.print(Text(gem_milestone, style=f"{color}"))
            console.print(f"[bold green]Hours: {hours:.2f}h[/bold green]")

            # Show breakdown of hours by description
            console.print()
            console.print("[bold]Breakdown:[/bold]")
            for entry in sorted(current_entries, key=lambda e: -e.hours):
                desc_display = entry.description if entry.description else "(no description)"
                if len(desc_display) > 40:
                    desc_display = desc_display[:37] + "..."

                # Show which original dates contributed
                orig_dates = sorted(set(entry.original_dates))
                shift_str = ""
                if orig_dates:
                    from_dates = orig_dates[0].strftime('%m/%d')
                    if len(orig_dates) > 1:
                        from_dates = f"{orig_dates[0].strftime('%m/%d')}-{orig_dates[-1].strftime('%m/%d')}"
                    if orig_dates[0] != day_date:
                        shift = (day_date - orig_dates[0]).days
                        shift_str = f" ({'+' if shift > 0 else ''}{shift}d)"
                    console.print(f"  [green]{entry.hours:.2f}h[/green] {desc_display} [dim]from {from_dates}{shift_str}[/dim]")
                else:
                    console.print(f"  [green]{entry.hours:.2f}h[/green] {desc_display}")

            if descriptions:
                console.print()
                # Check if any descriptions are split across multiple days
                note_parts = []
                for desc in sorted(descriptions):
                    # Find all days this description appears on for this assignment
                    desc_days = []
                    for e in week_entries:
                        if e.gem_assignment == assignment and e.description == desc:
                            if e.target_date not in desc_days:
                                desc_days.append(e.target_date)
                    desc_days = sorted(desc_days)

                    if len(desc_days) > 1:
                        # Split across multiple days - add part number
                        part_num = desc_days.index(day_date) + 1
                        total_parts = len(desc_days)
                        note_parts.append(f"{desc} (pt.{part_num}/{total_parts})")
                    else:
                        note_parts.append(desc)

                console.print("[bold]Note:[/bold] " + "; ".join(note_parts))

            # Wait for user
            if not wait_for_keypress(console):
                console.print("[yellow]Aborted by user.[/yellow]")
                return

    console.print()
    console.print(Panel.fit(
        f"[bold green]All {total_cells} cells completed![/bold green]\n"
        f"Total: {scheduled_total:.2f}h",
        border_style="green"
    ))

    # Offer to mark as billed
    if mark_billed_callback:
        console.print()
        try:
            response = console.input("[yellow]Mark all entries as billed in Toggl? (y/N): [/yellow]")
            if response.lower() == 'y':
                mark_billed_callback()
        except (KeyboardInterrupt, EOFError):
            pass
