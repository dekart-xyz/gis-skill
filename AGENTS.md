# AGENTS.md instructions for /Users/vladi/dev/gis-skill

## Skills
A skill is a set of local instructions to follow that is stored in a `SKILL.md` file.

### Available skills
- giskill: Build and optionally execute cost-safe Overture Maps SQL for BigQuery with dry-run budget checks. Use when users need map-ready SQL, executed results, or over-budget fallback options. (file: giskill/SKILL.md)

### How to use skills
- Trigger rules: If the user names the skill (`$giskill`) or the request clearly matches its description, use it for that turn.
- Loading: Open `giskill/SKILL.md` and follow it.
- Scope: Do not carry this skill across turns unless re-mentioned or clearly required by the new request.

## References
- Claude Skills docs: https://code.claude.com/docs/en/skills
- Agent Skills open standard: https://agentskills.io

## Skill Best Practices
- Keep frontmatter concise: use short `description`, include `argument-hint` when slash arguments are expected.
- Keep one canonical source per artifact: no duplicate `SKILL.md` or script logic copies.
- Put deterministic execution logic in `scripts/` and reference those scripts explicitly from `SKILL.md`.
- Keep instructions focused and scannable; move deep details to supporting files only when needed.
