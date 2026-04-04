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

## How it works

Once installed, Claude Code auto-discovers the skill and uses it to build cost-safe Overture Maps SQL for BigQuery. The skill guides Claude to call `bq` directly with dry-run budget checks, bbox scan gates, and ST_INTERSECTS for geographic correctness.

Requires: [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) with `bq` CLI authenticated.

## Dekart URL config

Set Dekart instance URL:

```bash
giskill dekart config --url http://localhost:3000
```

Show current effective URL:

```bash
giskill dekart config
```

Behavior:

- If no URL is configured, default is `https://cloud.dekart.xyz`
- Self-hosted users should set their own instance URL
- Local development should use `http://localhost:3000`
