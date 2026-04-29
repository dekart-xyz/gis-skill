# Eval Runbook

This runbook executes the full eval cycle in one command using Claude CLI.

## What this eval does

For each case in `evals/evals.json`:

1. Runs the task with `/geosql ...`.
2. In the same Claude session, asks Claude to validate all assertions.
3. Claude can run `bq`/`gcloud` commands while validating assertions.
4. Saves grading and logs.

Assertions are plain strings only.

## Prerequisites

- Claude CLI installed and authenticated (`claude --help` works).
- You are in `geosql`.

## One-command Eval

```bash
python3 evals/run.py --model claude-sonnet-4-6 --thinking-level high
```

By default, the runner prints a live trace of Claude IO (prompt, tool calls, tool outputs, final result) so you can see exactly what is happening.

Quiet mode:

```bash
python3 evals/run.py --model claude-sonnet-4-6 --thinking-level high --no-show-io
```

Adjust trace truncation length:

```bash
python3 evals/run.py --model claude-sonnet-4-6 --thinking-level high --io-max-chars 2000
```

Default permission behavior for this command:

- `--dangerously-skip-permissions` (unless `--safe-mode` is set)
- `--permission-mode bypassPermissions`
- `--allowedTools "Bash(bq:*) Bash(gcloud:*)"`

This is to avoid approval interruptions during assertion-time `bq` checks.

## Output Files

Per case:

- `prompt.txt` (skill prompt)
- `output.md` (first model answer)
- `assertion_prompt.txt` (follow-up grading prompt)
- `events.ndjson` (full stream events, generated locally)
- `model_messages.json` (all assistant/model messages, compact)
- `generation_result_event.json` (result event for first task run)
- `assertion_result_event.json` (result event for assertion grading run)
- `grading.json` (parsed assertion grading summary)

Aggregate:

- `evals/results/latest/benchmark.json`

## Exit Codes

- `0`: all assertions passed
- `1`: one or more assertions failed
- `2`: setup/runtime issue (for example no Claude binary)

## Optional Flags

Custom eval file:

```bash
python3 evals/run.py --evals evals/evals.json
```

Custom output dir:

```bash
python3 evals/run.py --out-dir evals/results/manual-run
```

Model and thinking level are required:

```bash
python3 evals/run.py --model claude-sonnet-4-6 --thinking-level xhigh
```

Safer permissions (may re-introduce approval prompts):

```bash
python3 evals/run.py --model claude-sonnet-4-6 --thinking-level high --safe-mode --permission-mode auto
```
