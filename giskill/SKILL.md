---
name: giskill
description: Build cost-safe Overture Maps SQL for BigQuery with mandatory dry-run budget checks and optional execution. Use for map-ready queries, numeric results, and over-budget fallback plans.
argument-hint: [task-or-query]
---

# GIS Skill (Claude)

Use this skill for Overture Maps work in BigQuery with strict cost controls.

## Non-Installation Rule

Never install software automatically. If dependencies are missing, report exact prerequisite commands for the user to run.

## Preferred Execution Path

Use the CLI command for deterministic behavior:

```bash
giskill query --query-file /path/to/query.sql --mode sql_only
```

Or:

```bash
giskill query --query "SELECT ..." --mode execute
```

Long command is also supported for compatibility:

```bash
giskill run-cost-checked-query --query "SELECT ..." --mode execute
```

The command already handles:
- Optional `.env` loading from current working directory
- `BQ_PROJECT_ID` fallback to `gcloud config get-value project`
- `BQ_LOCATION` optional passthrough
- `BQ_MAX_BYTES_BILLED` safe default `10737418240` (10 GiB)
- Optional auth env support: `GOOGLE_APPLICATION_CREDENTIALS`, `BIGQUERY_CREDENTIALS_BASE64`
- Mandatory dry run and bytes budget gate before execution

## Inputs

Collect or infer:
- `mode`: infer from user intent (`sql_only` for query drafting/verification, `execute` when user asks for actual numbers/results)
- User intent: dataset/theme, filters, output columns, aggregation, map vs numeric output
- Optional bounds: bbox, date/time, row limit
- Optional explicit over-budget override

## Guardrails

Apply all guardrails every time:
1. Run dry run before execution.
2. Enforce `maximum_bytes_billed`.
3. Prefer bounded SQL by default (bbox/date/limit, minimal selected columns).
4. If estimated bytes exceed budget and no explicit override: do not execute.
5. If over budget: provide lower-cost SQL variants.

## Query Construction Rules

1. Select only required columns; avoid `SELECT *`.
2. Prefer filtered Overture tables and partition-friendly predicates.
3. Add default limits when user omitted bounds.
4. Separate heavy geometry retrieval from numeric aggregation when practical.

## Mode Behavior

Decide mode automatically unless user explicitly requests one.

### `sql_only` (default)
- Build optimized SQL
- Run mandatory dry run
- Return SQL + estimated bytes + budget pass/fail

### `execute`
- Build optimized SQL
- Run mandatory dry run
- Execute only if user asked for results and estimate is within budget (or explicit user override)
- Return rows/aggregates preview + SQL

## Failure Handling

If `bq` unavailable or auth fails:
- Return exact fix commands only (no auto-install/no auto-auth side effects).

If over budget:
- Keep `status=blocked_over_budget`
- Do not execute query
- Return at least one cheaper SQL variant

If query invalid:
- Return corrected SQL draft and rerun dry-run logic

## Output Contract

Always return:
- `mode`
- `status` (`dry_run_only | executed | blocked_over_budget`)
- `project_id`
- `location`
- `estimated_bytes`
- `max_bytes_billed`
- `query_sql`
- `result_preview` (if executed)
- `next_steps`
