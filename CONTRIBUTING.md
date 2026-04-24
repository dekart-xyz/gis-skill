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
giskill install claude
```

## Dekart runtime CLI

Dekart integration moved to `dekart` CLI in `../dekart-cli`.

```bash
cd ../dekart-cli
pip install -e .
dekart --help
```

## Publish

```bash
pip install build twine
python -m build
twine upload dist/*
```
