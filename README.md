# gis-skill
Create maps and answer questions from your data.

## Install giskill (skill installer only)

```bash
pip install -e .
```

## Install Claude skill

```bash
giskill install claude
```

This installs to:

`~/.claude/skills/giskill/SKILL.md`

and copies references to:

`~/.claude/skills/giskill/references/`

## Dekart CLI

GIS skill uses the separate `dekart` CLI for Dekart auth, MCP tools, and file upload workflows.

Install `dekart` from the new repo:

```bash
cd ../dekart-cli
pip install -e .
dekart --help
```

Config is stored in:

- `~/.config/dekart/config.json`
- `~/.config/dekart/token.json`
