# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gemling is a CLI tool that transforms Toggl time tracking data into a cell-by-cell interactive guide for entering time into GEM (an internal time tracking system). It handles hour rounding, daily/weekly limits, and can mark entries as billed in Toggl.

## Build & Run Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run with CSV export and assignments file
python gemling.py data/toggl_export.csv -a data/assignments.yml

# Run with custom hour limits
python gemling.py export.csv --max-daily 7.5 --max-weekly 37.5

# Run with Toggl API integration (to mark entries as billed)
python gemling.py export.csv -t YOUR_TOGGL_API_TOKEN
```

## Project Architecture

```
gemling.py      # Main entry point, CLI argument handling
parser.py       # CSV/YAML parsing, data models (TogglEntry, AssignmentInfo)
scheduler.py    # Time redistribution logic, GemEntry creation
output.py       # Interactive terminal UI with Rich
toggl_api.py    # Toggl API client for marking entries as billed
```

### Data Flow
1. `parser.py` reads Toggl CSV → `TogglEntry` objects
2. `parser.py` reads assignments YAML → `AssignmentInfo` mappings
3. `scheduler.py` redistributes hours respecting limits → `GemEntry` objects
4. `output.py` displays interactive cell-by-cell guide

## Key Conventions

- Hours are rounded up to 0.25h increments (`ceil_to_quarter`)
- Weekend work shifts to nearest weekday (Sat→Fri, Sun→Mon)
- Private data goes in `data/` folder (gitignored)
- Test data in `test_data/` uses anonymized examples
- Colors in assignments.yml use Rich color names (green, blue, cyan, etc.)
