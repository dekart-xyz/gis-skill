# Contributing

## Setup

```bash
git clone https://github.com/dekart-xyz/gis-skill.git
cd gis-skill
pip install -e .
```

## Test locally

```bash
python -m giskill.cli --help
python -m giskill.cli install claude
```

After editable install, you can also use:

```bash
giskill install claude
```

## Publish

```bash
pip install build twine
python -m build
twine upload dist/*
```
