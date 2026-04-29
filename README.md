# geosql
Create maps and answer questions from your data.

Build instructions: `RUNBOOK.md`

## Install geosql (skill installer only)

```bash
pip install -e .
```

## Install via Skills CLI

```bash
npx skills add dekart-xyz/geosql
```

`npx skills add` uses the repository `geosql.skill` package.  
That package is generated from canonical sources in `geosql/` (no duplicated skill content):

```bash
python3 scripts/build_skill_package.py
```

## Install skill

Interactive (recommended):

```bash
geosql
```

Or explicit target:

```bash
geosql install claude
geosql install codex
geosql install all
```

Claude install path:

`~/.claude/skills/geosql/SKILL.md`

and copies references to:

`~/.claude/skills/geosql/references/`

Codex install path:

`~/.codex/skills/geosql/SKILL.md`

and copies references to:

`~/.codex/skills/geosql/references/`

## Dekart CLI

GeoSQL uses the separate `dekart` CLI for Dekart auth, MCP tools, and file upload workflows.

Install `dekart` from the new repo:

```bash
cd ../dekart-cli
pip install -e .
dekart --help
```

Config is stored in:

- `~/.config/dekart/config.json`
- `~/.config/dekart/token.json`
