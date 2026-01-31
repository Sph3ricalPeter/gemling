"""Data parsing module for Toggl CSV and assignments YAML."""

import csv
from dataclasses import dataclass
from datetime import date, time
from typing import Optional
import yaml


@dataclass
class TogglEntry:
    """Represents a single time entry from Toggl."""
    description: str
    duration_hours: float
    project: str
    start_date: date
    start_time: time
    member: str
    original_id: Optional[int] = None

    def __repr__(self) -> str:
        return f"TogglEntry({self.description!r}, {self.duration_hours}h, {self.project}, {self.start_date})"


def parse_duration(duration_str: str) -> float:
    """Parse duration string (H:MM:SS or HH:MM:SS) to decimal hours."""
    parts = duration_str.split(':')
    if len(parts) != 3:
        raise ValueError(f"Invalid duration format: {duration_str}")

    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])

    return hours + minutes / 60 + seconds / 3600


def parse_date(date_str: str) -> date:
    """Parse date string (YYYY-MM-DD) to date object."""
    parts = date_str.split('-')
    return date(int(parts[0]), int(parts[1]), int(parts[2]))


def parse_time(time_str: str) -> time:
    """Parse time string (HH:MM:SS) to time object."""
    parts = time_str.split(':')
    return time(int(parts[0]), int(parts[1]), int(parts[2]))


def get_column(row: dict, name: str) -> str:
    """Get column value, handling BOM and whitespace in headers."""
    # Try exact match first
    if name in row:
        return row[name]

    # Try case-insensitive and stripped match
    name_lower = name.lower().strip()
    for key, value in row.items():
        if key.lower().strip() == name_lower:
            return value

    raise KeyError(f"Column '{name}' not found. Available: {list(row.keys())}")


def parse_toggl_csv(filepath: str) -> list[TogglEntry]:
    """Parse Toggl CSV file into list of TogglEntry objects."""
    entries = []

    # Use utf-8-sig to handle BOM (Byte Order Mark) in CSV files
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entry = TogglEntry(
                description=get_column(row, 'Description'),
                duration_hours=parse_duration(get_column(row, 'Duration')),
                project=get_column(row, 'Project'),
                start_date=parse_date(get_column(row, 'Start date')),
                start_time=parse_time(get_column(row, 'Start time')),
                member=get_column(row, 'Member'),
            )
            entries.append(entry)

    return entries


@dataclass
class AssignmentInfo:
    """Mapping info for a Toggl project."""
    project: str  # GEM project name
    milestone: str  # GEM milestone name
    color: str


def parse_assignments(filepath: str) -> dict[str, AssignmentInfo]:
    """Parse assignments YAML file into project -> AssignmentInfo mapping."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    assignments = {}
    raw = data.get('assignments', {})

    for toggl_project, value in raw.items():
        if isinstance(value, dict):
            # New format: {project: "...", milestone: "...", color: "..."}
            assignments[toggl_project] = AssignmentInfo(
                project=value.get('project', toggl_project),
                milestone=value.get('milestone', ''),
                color=value.get('color', 'white'),
            )
        else:
            # Old format: just a string (treat as project name)
            assignments[toggl_project] = AssignmentInfo(
                project=value,
                milestone='',
                color='white',
            )

    return assignments
