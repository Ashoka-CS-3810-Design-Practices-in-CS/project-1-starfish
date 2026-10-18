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
