# Build Runbook

This runbook explains how to build all GeoSQL deliverables from source.

## Prerequisites

- Python 3.8+
- `pip`

## 1) Build Python package (wheel + sdist)

From repo root:

```bash
pip install build
python3 -m build
```

Artifacts:

- `dist/geosql-<version>-py3-none-any.whl`
- `dist/geosql-<version>.tar.gz`

## 2) Build Skills CLI package (`geosql.skill`)

From repo root:

```bash
python3 scripts/build_skill_package.py
```

Artifact:

- `geosql.skill`

The package is generated from canonical sources only:

- `geosql/SKILL.md`
- `geosql/references/*`

## 3) Smoke test local CLI

```bash
pip install -e .
python3 -m geosql --help
geosql --help
```

## 4) Smoke test installer paths

Explicit installs:

```bash
geosql install claude
geosql install codex
```

Expected paths:

- `~/.claude/skills/geosql/SKILL.md`
- `~/.codex/skills/geosql/SKILL.md`

## 5) Verify repository contains no legacy naming

```bash
rg -n "giskill|gis-skill" .
```

Expected result: no matches.

## 6) Configure pre-push release hook (main branch)

Install hooks path:

```bash
./scripts/install_hooks.sh
```

The `pre-push` hook runs only on `main` and performs:

1. Rebuild `geosql.skill` and commit if changed.
2. Bump minor version in `pyproject.toml` and commit (separate commit).
3. Build package and publish to PyPI.
4. Exit with non-zero so you run `git push` again and include the new commits.

Required environment variable:

```bash
export PYPI_API_TOKEN='pypi-...'
```

Recommended push flow on `main`:

```bash
git push         # hook runs, creates commits, publishes, exits non-zero intentionally
git push         # push new local commits
```
