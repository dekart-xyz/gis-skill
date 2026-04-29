# geosql
Create maps and answer questions from your data.

## Install geosql (skill installer only)

```bash
pip install -e .
```

## Install Claude skill

```bash
geosql install claude
```

This installs to:

`~/.claude/skills/geosql/SKILL.md`

and copies references to:

`~/.claude/skills/geosql/references/`

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
