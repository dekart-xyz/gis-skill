# gis-skill
Create maps and answer questions from your data.

## Install Claude skill

```bash
giskill install claude
```

This installs to:

`~/.claude/skills/giskill/SKILL.md`

## Local Claude skill source

Canonical skill instructions are in:

`giskill/SKILL.md`

## Cost-Checked Query Command

Run cost-aware BigQuery SQL directly from CLI:

```bash
giskill query --query-file /path/to/query.sql --mode sql_only
```

Long command is also supported:

```bash
giskill run-cost-checked-query --query-file /path/to/query.sql --mode sql_only
```
