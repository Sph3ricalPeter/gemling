# Gemling

A CLI tool that transforms Toggl time tracking data into a cell-by-cell interactive guide for entering time into GEM.

## Features

- **Smart Hour Rounding**: Rounds hours up to 0.25h increments
- **Daily/Weekly Limits**: Respects configurable max hours per day (default 8h) and week (default 40h)
- **Weekend Handling**: Automatically shifts weekend work to nearest weekday
- **Interactive Guide**: Cell-by-cell walkthrough matching GEM's weekly grid layout
- **Split Tracking**: Shows part numbers when entries span multiple days (pt.1/2, pt.2/2)
- **Toggl Integration**: Optionally mark entries as billed via Toggl API

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

1. **Parse**: Reads Toggl CSV and assignments YAML
2. **Schedule**: Redistributes hours to fit daily/weekly limits while minimizing date shifts
3. **Guide**: Displays interactive weekly grid, highlighting each cell to enter
4. **Mark Billed** (optional): Adds "gem-billed" tag to processed entries in Toggl

### Scheduling Algorithm

- Places entries on their original (or nearest working) day
- Moves overflow to adjacent days with capacity
- Prefers minimal date shifts (max 7 working days by default)
- Combines entries with same description/project on same day
- Splits large entries across days when needed

## License

MIT
