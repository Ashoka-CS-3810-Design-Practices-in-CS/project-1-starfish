# Delhi Metro Route Planner

Interactive Delhi Metro route planner and visualiser.
CS-3810 Design Practices in CS, Ashoka University — Project 1, Team Starfish (Sanjana Shenai, Arav Kapoor).

## Setup

Requires Python 3.12.

```bash
pip install -e ".[test]"
```

## Run

```bash
python main.py
```

## Test

```bash
pytest                 # everything
pytest -m "not slow"   # skip the all-pairs oracle on the real data
```

## Command-line routing

```bash
python tools/route_cli.py data "Rajiv Chowk" "Hauz Khas"
python tools/route_cli.py data "Dwarka Sector 21" "Botanical Garden" fewest_changes
```

## Desktop build (optional)

```bash
pip install -e ".[build]"
pyinstaller packaging/metro.spec   # output in dist/DelhiMetroPlanner/
```

## Updating the network data

Edit the CSV files in `data/source/`, then regenerate the JSON and re-run the tests:

```bash
python tools/csv_to_json.py data/source data
pytest
```

See `data/README.md` for where each field comes from and what is still unverified.
