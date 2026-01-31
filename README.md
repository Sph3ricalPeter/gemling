# Gemling

A CLI tool that transforms Toggl time tracking data into a cell-by-cell interactive guide for entering time into GEM.

**Stop copying hours manually.** Gemling reads your Toggl export, intelligently redistributes hours to fit daily/weekly limits, and walks you through each cell to enter in GEM.

## Features

| Feature | Description |
|---------|-------------|
| **Smart Rounding** | Rounds hours up to 0.25h increments |
| **Limits** | Respects max hours per day (8h) and week (40h) |
| **Weekend Shift** | Automatically moves weekend work to weekdays |
| **Interactive Guide** | Cell-by-cell walkthrough with visual grid |
| **Split Tracking** | Shows part numbers when entries span days |
| **Toggl Sync** | Mark entries as billed via Toggl API |

## Installation

```bash
pip install -r requirements.txt
```

Requirements:
- Python 3.10+
- pyyaml
- requests
- rich

## Usage

### Basic Usage

```bash
python gemling.py toggl_export.csv -a assignments.yml
```

### With Custom Hour Limits

```bash
python gemling.py export.csv --max-daily 7.5 --max-weekly 37.5
```

### With Toggl API (Mark as Billed)

```bash
python gemling.py export.csv -t YOUR_TOGGL_API_TOKEN
```

## Example Output

### Summary View

When you run Gemling, you first see a summary of all entries:

```
╭─────── === GEM Time Entry Guide === ───────╮
│ Toggl total: 42.50h                        │
│ GEM total:   43.00h (+0.50h after rounding)│
│ Entries:     12                            │
╰────────────────────────────────────────────╯

Projects:
  Alpha Platform / Q1 Sprint: 28.00h
  Beta Maintenance / Support: 15.00h

Descriptions:
 #  Toggl Project  GEM Project / Milestone      Description         Total  GEM Output                   From   Ops
01  ProjectX       Alpha Platform / Q1 Sprint   API integration    12.00h  01/27 4.00h | 01/28 8.00h  01/26-27  +0.25h split +1d
02  ProjectX       Alpha Platform / Q1 Sprint   Code review         8.00h  01/27 4.00h | 01/28 4.00h  01/26     split
03  ProjectY       Beta Maintenance / Support   Bug fixes           7.00h  01/30 4.00h | 01/31 3.00h  01/30     +0.25h

Week Distribution:
     Mon  Tue  Wed  Thu  Fri   Total  IDs
W05  ████ ████ ████ ████ ██░░  35.00h 01,02,03
W06  ████ ░░░░ ░░░░ ░░░░ ░░░░   8.00h 01
```

### Interactive Cell Guide

Then Gemling walks you through each cell to enter:

```
╭─ Week 1/2: Week 05 (Jan 27 - Jan 31) ─╮
╰───────────────────────────────────────╯

Project / Assignment              Mon    Tue    Wed    Thu    Fri    Total
> Alpha Platform / Q1 Sprint     [8.00]  8.00   8.00   4.00    -     28.00
  Beta Maintenance / Support       -      -      -     4.00   3.00    7.00
TOTAL                             8.00   8.00   8.00   8.00   3.00   35.00

[1/8] Mon 01/27
Project: Alpha Platform
Milestone: Q1 Sprint
Hours: 8.00h

Breakdown:
  4.00h API integration work from 01/27
  4.00h Code review from 01/26 (+1d)

Press Space or Enter to continue (q to quit)...
```

### Visual Indicators

- `[8.00]` — Current cell to enter (highlighted)
- `>` — Current row being processed
- `(+1d)` — Entry was shifted from another day
- `(pt.1/2)` — Entry split across multiple days

## Configuration

### Assignments File

Create a YAML file mapping Toggl project names to GEM projects/milestones:

```yaml
assignments:
  "Toggl Project Name":
    project: "GEM Project Name"
    milestone: "GEM Milestone"
    color: cyan

  "Another Project":
    project: "Another GEM Project"
    milestone: "Sprint 1"
    color: green
```

Available colors: Any [Rich color name](https://rich.readthedocs.io/en/stable/appendix/colors.html) (red, green, blue, cyan, magenta, yellow, white, etc.)

### Private Data

For real data, create a `data/` folder (gitignored):

```
data/
  toggl_export.csv      # Your Toggl export
  assignments.yml       # Your project mappings
```

Then run:

```bash
python gemling.py data/toggl_export.csv -a data/assignments.yml
```

## Toggl CSV Export

Export from Toggl Track:
1. Go to Reports → Detailed
2. Select date range
3. Click Export → Download CSV

Required columns: `Description`, `Duration`, `Project`, `Start date`, `Start time`, `Member`

## How It Works

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  Toggl CSV  │───▶│  Scheduler  │───▶│   Weekly    │───▶│  Mark as    │
│  + YAML     │    │  Algorithm  │    │   Guide     │    │  Billed     │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
     Parse          Redistribute        Interactive        (optional)
```

1. **Parse** — Reads Toggl CSV export and assignments YAML
2. **Schedule** — Redistributes hours to fit daily/weekly limits
3. **Guide** — Interactive weekly grid, highlighting each cell
4. **Mark Billed** — Adds "gem-billed" tag to Toggl entries

### Scheduling Algorithm

The scheduler tries to keep hours on their original dates while respecting limits:

| Priority | Action |
|----------|--------|
| 1 | Place on original day (or nearest weekday for weekends) |
| 2 | Move overflow to adjacent days with capacity |
| 3 | Split large entries across multiple days |
| 4 | Combine same description/project entries on same day |

Maximum shift is 7 working days by default.

## Quick Start

```bash
# 1. Install
pip install -r requirements.txt

# 2. Export from Toggl (Reports → Detailed → Export CSV)

# 3. Create assignments.yml mapping Toggl projects to GEM
cat > assignments.yml << 'EOF'
assignments:
  "My Toggl Project":
    project: "GEM Project Name"
    milestone: "Sprint 1"
    color: cyan
EOF

# 4. Run
python gemling.py toggl_export.csv -a assignments.yml
```

## License

MIT
