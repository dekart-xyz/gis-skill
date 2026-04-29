# Contributing

## Setup

```bash
git clone https://github.com/dekart-xyz/geosql.git
cd geosql
pip install -e .
```

## Test locally

```bash
python -m geosql --help
python -m geosql install claude
python -m geosql install codex
geosql
geosql install all
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
