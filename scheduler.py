"""Time redistribution logic for GEM entries."""

import math
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from heapq import heappush, heappop

from parser import TogglEntry, AssignmentInfo


@dataclass
class OriginalEntry:
    """Tracks an original Toggl entry for display purposes."""
    date: date
    raw_hours: float  # Before rounding
    rounded_hours: float  # After rounding to 0.5


@dataclass
class GemEntry:
    """Represents a time entry to be made in GEM."""
    hours: float
    gem_project: str  # GEM project name
    gem_milestone: str  # GEM milestone name
    target_date: date
    description: str
    toggl_project: str  # Original Toggl project name
    color: str = "white"  # Color for display
    entry_count: int = 1  # Number of original Toggl entries combined
    original_dates: list[date] = field(default_factory=list)  # Original Toggl dates
    original_entries: list[OriginalEntry] = field(default_factory=list)  # Detailed original entries

    @property
    def gem_assignment(self) -> str:
        """Combined project/milestone for display and grouping."""
        if self.gem_milestone:
            return f"{self.gem_project} / {self.gem_milestone}"
        return self.gem_project

    def __repr__(self) -> str:
        return f"GemEntry({self.hours}h, {self.gem_project}/{self.gem_milestone}, {self.target_date})"


def ceil_to_quarter(value: float) -> float:
    """Round up to nearest 0.25 (e.g., 3.12 -> 3.25, 3.26 -> 3.5)."""
    return math.ceil(value * 4) / 4


def get_nearest_working_day(d: date) -> date:
    """Get the nearest working day (Mon-Fri). If weekend, go to Monday."""
    while d.weekday() >= 5:  # Saturday = 5, Sunday = 6
        d += timedelta(days=1)
    return d


def get_nearest_working_day_in_month(d: date) -> date:
    """Get the nearest working day within the same month. Prefer forward, then backward."""
    original_month = d.month
    original_year = d.year

    # If already a working day, return it
    if d.weekday() < 5:
        return d

    # Try forward first (but stay in month)
    forward = d
    while forward.weekday() >= 5:
        forward += timedelta(days=1)
        if forward.month != original_month or forward.year != original_year:
            break
    else:
        return forward

    # Forward went out of month, try backward
    backward = d
    while backward.weekday() >= 5:
        backward -= timedelta(days=1)
        if backward.month != original_month or backward.year != original_year:
            # Both directions fail (shouldn't happen in practice)
            return d
    return backward


def get_next_working_day(d: date) -> date:
    """Get the next working day after d."""
    max_date = date(9999, 12, 30)  # Safety limit
    next_day = d + timedelta(days=1)
    while next_day.weekday() >= 5 and next_day < max_date:
        next_day += timedelta(days=1)
    return min(next_day, max_date)


def get_prev_working_day(d: date) -> date:
    """Get the previous working day before d."""
    prev_day = d - timedelta(days=1)
    while prev_day.weekday() >= 5:
        prev_day -= timedelta(days=1)
    return prev_day


def working_days_between(d1: date, d2: date) -> int:
    """Count working days between two dates (absolute difference)."""
    if d1 > d2:
        d1, d2 = d2, d1
    count = 0
    current = d1
    while current < d2:
        current += timedelta(days=1)
        if current.weekday() < 5:
            count += 1
    return count


def get_week_number(d: date) -> tuple[int, int]:
    """Get (year, week_number) for a date using ISO calendar."""
    iso = d.isocalendar()
    return (iso[0], iso[1])


def same_month(d1: date, d2: date) -> bool:
    """Check if two dates are in the same month."""
    return d1.year == d2.year and d1.month == d2.month


def schedule_entries(
    toggl_entries: list[TogglEntry],
    assignments: dict[str, AssignmentInfo],
    max_hours_per_day: float = 8.0,
    max_hours_per_week: float = 40.0,
    min_entry_hours: float = 0.5,
    max_shift_days: int = 7,
) -> tuple[list[GemEntry], float, float]:
    """
    Schedule Toggl entries into GEM entries respecting daily/weekly limits.

    Algorithm:
    1. Place entries on their preferred working day (original or nearest)
    2. Process days in chronological order
    3. For overloaded days, move excess to the nearest day with capacity
    4. Respect max_shift_days limit when possible, but allow exceeding if necessary

    Returns: (gem_entries, original_total, scheduled_total)
    """
    if not toggl_entries:
        return [], 0.0, 0.0

    # Calculate original total before rounding
    original_total = sum(e.duration_hours for e in toggl_entries)

    # Build work items - one per entry, preserving original date
    @dataclass
    class WorkItem:
        original_date: date
        preferred_date: date  # Working day for scheduling
        rounded_hours: float
        raw_hours: float
        description: str
        toggl_project: str
        gem_project: str
        gem_milestone: str
        color: str
        item_id: int = 0

    work_items: list[WorkItem] = []

    for i, entry in enumerate(toggl_entries):
        info = assignments.get(entry.project)
        if info:
            gem_project = info.project
            gem_milestone = info.milestone
            color = info.color
        else:
            gem_project = f"UNMAPPED: {entry.project}"
            gem_milestone = ""
            color = "white"

        # For weekends, prefer the closer weekday based on day of week
        if entry.start_date.weekday() == 5:  # Saturday -> Friday
            preferred = entry.start_date - timedelta(days=1)
        elif entry.start_date.weekday() == 6:  # Sunday -> Monday
            preferred = entry.start_date + timedelta(days=1)
        else:
            preferred = entry.start_date

        # Ensure preferred date is in the same month
        if preferred.month != entry.start_date.month:
            preferred = get_nearest_working_day_in_month(entry.start_date)

        work_items.append(WorkItem(
            original_date=entry.start_date,
            preferred_date=preferred,
            rounded_hours=ceil_to_quarter(entry.duration_hours),
            raw_hours=entry.duration_hours,
            description=entry.description,
            toggl_project=entry.project,
            gem_project=gem_project,
            gem_milestone=gem_milestone,
            color=color,
            item_id=i,
        ))

    # Sort by preferred date
    work_items.sort(key=lambda w: w.preferred_date)

    # Get all working days in the month
    def get_month_working_days(d: date) -> list[date]:
        month_start = date(d.year, d.month, 1)
        if d.month == 12:
            next_month_start = date(d.year + 1, 1, 1)
        else:
            next_month_start = date(d.year, d.month + 1, 1)
        days = []
        scan = month_start
        while scan < next_month_start:
            if scan.weekday() < 5:
                days.append(scan)
            scan += timedelta(days=1)
        return days

    if not work_items:
        return [], 0.0, 0.0

    working_days = get_month_working_days(work_items[0].original_date)
    day_index = {d: i for i, d in enumerate(working_days)}

    # Determine the usable day range: only days within max_shift_days of original work
    original_preferred_dates = set(item.preferred_date for item in work_items)
    min_orig_idx = min(day_index.get(d, 0) for d in original_preferred_dates if d in day_index)
    max_orig_idx = max(day_index.get(d, len(working_days)-1) for d in original_preferred_dates if d in day_index)

    # Expand range by max_shift_days but stay within month
    usable_start_idx = max(0, min_orig_idx - max_shift_days)
    usable_end_idx = min(len(working_days) - 1, max_orig_idx + max_shift_days)
    usable_days = set(working_days[usable_start_idx:usable_end_idx + 1])

    # Structure: day -> list of {item, hours, orig_entry}
    day_entries: dict[date, list[dict]] = defaultdict(list)

    # Phase 1: Initial placement on preferred dates
    for item in work_items:
        orig_entry = OriginalEntry(
            date=item.original_date,
            raw_hours=item.raw_hours,
            rounded_hours=item.rounded_hours,
        )
        day_entries[item.preferred_date].append({
            "item": item,
            "hours": item.rounded_hours,
            "orig_entry": orig_entry,
        })

    def get_day_total(d: date) -> float:
        return sum(e["hours"] for e in day_entries[d])

    def get_week_total(d: date) -> float:
        week_key = get_week_number(d)
        return sum(
            get_day_total(wd) for wd in working_days
            if get_week_number(wd) == week_key
        )

    def get_available_capacity(d: date) -> float:
        if d not in usable_days:
            return 0
        day_cap = max(0, max_hours_per_day - get_day_total(d))
        week_cap = max(0, max_hours_per_week - get_week_total(d))
        return min(day_cap, week_cap)

    def calc_shift(orig_date: date, target: date) -> int:
        """Calculate shift in working days from original to target."""
        # For weekends, calculate from the preferred working day
        if orig_date.weekday() == 5:  # Saturday
            base = orig_date - timedelta(days=1)
        elif orig_date.weekday() == 6:  # Sunday
            base = orig_date + timedelta(days=1)
        else:
            base = orig_date
        return working_days_between(base, target)

    # Phase 2: Redistribute overflow using bidirectional search
    # Process in multiple passes with increasing search radius
    for pass_num in range(len(working_days)):
        made_change = False

        # Find all overloaded days
        overloaded = [(d, get_day_total(d) - max_hours_per_day)
                      for d in working_days
                      if get_day_total(d) > max_hours_per_day + 0.01]

        if not overloaded:
            break

        # Process most overloaded day
        overloaded.sort(key=lambda x: -x[1])
        day = overloaded[0][0]
        day_idx = day_index[day]

        # Find the best entry to move
        best_move = None
        best_score = (float('inf'), float('inf'))  # (shift, -hours)

        for entry in day_entries[day]:
            hours = entry["hours"]
            orig_date = entry["orig_entry"].date

            # Search for target days in order of distance from current day
            for dist in range(1, len(working_days)):
                for direction in [1, -1]:  # Forward first for ties
                    target_idx = day_idx + (dist * direction)
                    if not (0 <= target_idx < len(working_days)):
                        continue

                    target = working_days[target_idx]
                    cap = get_available_capacity(target)

                    if cap >= hours:
                        shift = calc_shift(orig_date, target)
                        # Skip if shift exceeds max_shift_days
                        if shift > max_shift_days:
                            continue
                        score = (shift, -hours)  # Prefer smaller shift, larger entries
                        if score < best_score:
                            best_score = score
                            best_move = (entry, target, hours)

                # If found a good move at this distance, check if we should take it
                if best_move and best_score[0] <= dist + 1:
                    break

            if best_move and best_score[0] <= 2:  # Take very good moves immediately
                break

        # If no whole entry fits, try splitting
        if not best_move:
            splittable = [e for e in day_entries[day] if e["hours"] > min_entry_hours * 2]
            if splittable:
                for dist in range(1, len(working_days)):
                    for direction in [1, -1]:
                        target_idx = day_idx + (dist * direction)
                        if not (0 <= target_idx < len(working_days)):
                            continue

                        target = working_days[target_idx]
                        cap = get_available_capacity(target)

                        if cap >= min_entry_hours:
                            # Find best entry to split
                            for entry in sorted(splittable, key=lambda e: -e["hours"]):
                                shift = calc_shift(entry["orig_entry"].date, target)
                                # Skip if shift exceeds max_shift_days
                                if shift > max_shift_days:
                                    continue
                                split_hours = min(cap, entry["hours"] - min_entry_hours)
                                split_hours = math.floor(split_hours * 4) / 4
                                if split_hours >= min_entry_hours:
                                    score = (shift, -split_hours)
                                    if score < best_score:
                                        best_score = score
                                        best_move = (entry, target, split_hours)
                                        break

                    if best_move:
                        break

        # Execute the move
        if best_move:
            entry, target, hours_to_move = best_move
            if hours_to_move >= entry["hours"] - 0.01:
                # Move whole entry
                day_entries[day].remove(entry)
                day_entries[target].append(entry)
            else:
                # Split entry
                entry["hours"] -= hours_to_move
                new_entry = {
                    "item": entry["item"],
                    "hours": hours_to_move,
                    "orig_entry": entry["orig_entry"],
                }
                day_entries[target].append(new_entry)
            made_change = True

        if not made_change:
            break

    # Phase 3: Final balancing - pull from overloaded adjacent days
    for _ in range(len(working_days) * 2):
        made_change = False

        for i, day in enumerate(working_days):
            cap = get_available_capacity(day)
            if cap < min_entry_hours:
                continue

            # Check adjacent days
            for dist in [1, -1, 2, -2]:
                adj_idx = i + dist
                if not (0 <= adj_idx < len(working_days)):
                    continue

                adj_day = working_days[adj_idx]
                if get_day_total(adj_day) <= max_hours_per_day:
                    continue

                # Move entries that would reduce shift
                for entry in list(day_entries[adj_day]):
                    if entry["hours"] > cap:
                        continue

                    orig_date = entry["orig_entry"].date
                    old_shift = calc_shift(orig_date, adj_day)
                    new_shift = calc_shift(orig_date, day)

                    if new_shift <= old_shift:
                        day_entries[adj_day].remove(entry)
                        day_entries[day].append(entry)
                        cap -= entry["hours"]
                        made_change = True

                        if cap < min_entry_hours:
                            break

        if not made_change:
            break

    # Phase 4: Convert to GemEntry objects
    gem_entries_map: dict[tuple[date, str, str, str], GemEntry] = {}

    for day, entries in day_entries.items():
        for entry in entries:
            item = entry["item"]
            hours = entry["hours"]
            orig_entry = entry["orig_entry"]

            if hours <= 0:
                continue

            entry_key = (day, item.description, item.gem_project, item.gem_milestone)
            if entry_key in gem_entries_map:
                gem_entries_map[entry_key].hours += hours
                gem_entries_map[entry_key].original_dates.append(item.original_date)
                gem_entries_map[entry_key].original_entries.append(orig_entry)
                gem_entries_map[entry_key].entry_count += 1
            else:
                gem_entries_map[entry_key] = GemEntry(
                    hours=hours,
                    gem_project=item.gem_project,
                    gem_milestone=item.gem_milestone,
                    target_date=day,
                    description=item.description,
                    toggl_project=item.toggl_project,
                    color=item.color,
                    entry_count=1,
                    original_dates=[item.original_date],
                    original_entries=[orig_entry],
                )

    # Convert to list and sort
    gem_entries = list(gem_entries_map.values())
    for entry in gem_entries:
        entry.original_dates = sorted(entry.original_dates)
        entry.original_entries = sorted(entry.original_entries, key=lambda e: e.date)

    gem_entries.sort(key=lambda e: (e.target_date, e.gem_project, e.gem_milestone, e.description))

    scheduled_total = sum(e.hours for e in gem_entries)
    return gem_entries, original_total, scheduled_total
