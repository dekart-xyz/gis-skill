# Contributing

## Setup

```bash
git clone https://github.com/dekart-xyz/gis-skill.git
cd gis-skill
pip install -e .
```

## Test locally

```bash
python -m giskill --help
python -m giskill install claude
python -m giskill query --query "SELECT 1" --mode sql_only
```

After editable install, you can also use:

```bash
giskill install claude
giskill query --query "SELECT 1" --mode sql_only
```

## Publish

```bash
pip install build twine
python -m build
twine upload dist/*
```
