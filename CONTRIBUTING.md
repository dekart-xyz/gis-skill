# Contributing

## Setup

```bash
git clone https://github.com/dekart-xyz/gis-skill.git
cd gis-skill
pip install -e .
```

## Test locally

```bash
giskill
```

## Publish

```bash
pip install build twine
python -m build
twine upload dist/*
```
