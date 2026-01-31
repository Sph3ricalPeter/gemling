"""Anonymize Toggl CSV exports for sharing/testing."""

import argparse
import csv
import re
import sys
from pathlib import Path


def make_consistent_id(value: str, prefix: str, mapping: dict[str, str]) -> str:
    """Generate a consistent anonymized ID for a value."""
    if not value or value == "-":
        return value
    if value not in mapping:
        mapping[value] = f"{prefix}{len(mapping) + 1}"
    return mapping[value]


def anonymize_toggl_csv(
    input_path: str,
    output_path: str | None = None,
    description_replacements: dict[str, str] | None = None,
) -> str:
    """
    Anonymize a Toggl CSV export.

    Replaces:
    - Member names -> User1, User2, etc.
    - Emails -> user1@example.com, etc.
    - Project names -> Project1, Project2, etc.
    - Client names -> Client1, Client2, etc.
    - Descriptions -> "Task" (generic), or apply custom replacements
    - Teams -> Team1, Team2, etc.

    Preserves:
    - All time/duration data (critical for scheduler testing)
    - Tags (usually not identifying)
    - Date structures

    Args:
        description_replacements: Dict of {pattern: replacement} for descriptions.
                                  If None, descriptions become "Task".
    """
    if description_replacements is None:
        description_replacements = {}
    input_file = Path(input_path)
    if output_path is None:
        output_path = input_file.parent / f"{input_file.stem}_anonymized{input_file.suffix}"

    # Mappings for consistent anonymization
    member_map: dict[str, str] = {}
    email_map: dict[str, str] = {}
    project_map: dict[str, str] = {}
    client_map: dict[str, str] = {}
    team_map: dict[str, str] = {}

    rows = []

    with open(input_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames

        for row in reader:
            anon_row = row.copy()

            # Anonymize member
            if 'Member' in row:
                anon_row['Member'] = make_consistent_id(row['Member'], 'User', member_map)

            # Anonymize email (keep domain structure)
            if 'Email' in row:
                member_id = member_map.get(row.get('Member', ''), 'user')
                if row['Email'] and row['Email'] != '-':
                    anon_row['Email'] = f"{member_id.lower()}@example.com"
                else:
                    anon_row['Email'] = row['Email']

            # Anonymize project
            if 'Project' in row:
                anon_row['Project'] = make_consistent_id(row['Project'], 'Project', project_map)

            # Anonymize client
            if 'Client' in row:
                anon_row['Client'] = make_consistent_id(row['Client'], 'Client', client_map)

            # Anonymize teams
            if 'Teams' in row:
                anon_row['Teams'] = make_consistent_id(row['Teams'], 'Team', team_map)

            # Anonymize description
            if 'Description' in row:
                if description_replacements:
                    # Apply custom replacements (case-insensitive)
                    desc = row['Description']
                    for pattern, replacement in description_replacements.items():
                        desc = re.sub(re.escape(pattern), replacement, desc, flags=re.IGNORECASE)
                    anon_row['Description'] = desc
                else:
                    # Default: replace with generic
                    anon_row['Description'] = 'Task'

            rows.append(anon_row)

    # Write anonymized data (quote all fields to match Toggl export format)
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
        writer.writeheader()
        writer.writerows(rows)

    # Print mapping summary (so you know what maps to what, but don't share this!)
    print(f"Anonymized {len(rows)} rows")
    print(f"\nMappings (keep private!):")
    print(f"  Members: {len(member_map)} unique")
    print(f"  Projects: {len(project_map)} unique")
    print(f"  Clients: {len(client_map)} unique")
    print(f"\nOutput written to: {output_path}")

    return str(output_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Anonymize Toggl CSV exports for safe sharing.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python anonymize_toggl.py data.csv
  python anonymize_toggl.py data.csv -o output.csv
  python anonymize_toggl.py data.csv -r "ACME Corp=Company" -r "John Smith=Person"
  python anonymize_toggl.py data.csv -r "SecretProject=Project"
        """,
    )
    parser.add_argument("input", help="Input CSV file")
    parser.add_argument("-o", "--output", help="Output CSV file (default: <input>_anonymized.csv)")
    parser.add_argument(
        "-r", "--replace",
        action="append",
        metavar="PATTERN=REPLACEMENT",
        help="Replace PATTERN with REPLACEMENT in descriptions (case-insensitive). "
             "Can be specified multiple times. If not specified, descriptions become 'Task'.",
    )

    args = parser.parse_args()

    # Parse replacements
    replacements = {}
    if args.replace:
        for r in args.replace:
            if "=" not in r:
                print(f"Error: Invalid replacement format '{r}'. Use PATTERN=REPLACEMENT")
                sys.exit(1)
            pattern, replacement = r.split("=", 1)
            replacements[pattern] = replacement

    anonymize_toggl_csv(args.input, args.output, replacements if replacements else None)
