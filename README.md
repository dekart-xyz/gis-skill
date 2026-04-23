# gis-skill
Create maps and answer questions from your data.

## Install Claude skill

```bash
giskill install claude
```

This installs to:

`~/.claude/skills/giskill/SKILL.md`

Install copies the canonical skill file as-is. The skill uses plain `bq` and `giskill` commands.

## Local Claude skill source

Canonical skill instructions are in:

`giskill/SKILL.md`

## How it works

Once installed, Claude Code auto-discovers the skill and uses it to build cost-safe Overture Maps SQL for BigQuery.

Requires: [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) with `bq` CLI authenticated.

The skill calls `bq query ...` and `giskill ...` using your shell environment.

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

## Dekart CLI authorization

Authorize this CLI against configured Dekart instance:

```bash
giskill dekart init
```

## Dekart MCP tools (dynamic)

List currently available MCP tools from your configured Dekart instance:

```bash
giskill dekart tools
```

Print raw JSON tool catalog (including input schemas):

```bash
giskill dekart tools --json
```

Print only tool names:

```bash
giskill dekart tools --names
```

Filter tools by name substring (case-insensitive):

```bash
giskill dekart tools --match upload
```

Print one tool schema by exact name:

```bash
giskill dekart tools --schema create_file --json
```

List tool argument keys (discoverable helper for agents):

```bash
giskill dekart tools --arg-keys
```

Call any MCP tool dynamically (no hardcoded CLI-side schema):

```bash
giskill dekart call --name create_report --args '{}'
```

Example with arguments:

```bash
giskill dekart call --name create_dataset --args '{"report_id":"<report-id>"}'
```

Extract scalar values directly (no `jq`):

```bash
giskill dekart call --name create_report --args '{}' --extract result.report.id
```

Write response payload to file without shell redirection:

```bash
giskill dekart call --name start_file_upload_session --args '{"file_id":"<file-id>","name":"giskill-upload.csv","mime_type":"text/csv","total_size":12345}' --json --out /tmp/start.json
```

## Multipart upload helper (MCP-first)

Control plane stays in MCP calls. CLI only automates binary part PUTs.

Single-command flow (recommended):

```bash
giskill dekart upload-file --file /tmp/giskill-upload.csv --file-id <file-id> --name giskill-upload.csv --mime-type text/csv --json --out /tmp/upload-result.json
```

This command performs start session + part uploads + complete under the hood.

1. Start session via MCP:

```bash
giskill dekart call --name start_file_upload_session --args '{"file_id":"<file-id>","name":"giskill-upload.csv","mime_type":"text/csv","total_size":12345}' --json > /tmp/start.json
```

2. Upload parts from local file:

```bash
giskill dekart upload-parts --file /tmp/giskill-upload.csv --start-response-file /tmp/start.json --file-id <file-id> --complete-args-out /tmp/complete-args.json --json > /tmp/parts.json
```

3. Complete session via MCP using returned parts:

```bash
giskill dekart call --name complete_file_upload_session --args '{"file_id":"<file-id>","upload_session_id":"<upload-session-id>","parts":[...],"total_size":12345}' --json
```

You can also pass explicit values instead of `--start-response-file`:

```bash
giskill dekart upload-parts --file /tmp/giskill-upload.csv --upload-part-endpoint '/api/v1/file/.../parts/{part_number}' --max-part-size 24000000 --required-headers-json '[]'
```

Flow:

- CLI registers a device session at `/api/v1/device`
- Browser opens `/device/authorize?device_id=...`
- After login and authorization, CLI polls `/api/v1/device/token`
- JWT is saved to `~/.config/giskill/token.json`

## Troubleshooting

Quick checks:

```bash
which giskill
giskill --help

which bq
bq version
```

If `giskill` is not found:

```bash
python3 -m pip install -e .
python3 -m giskill --help
```

If `bq query` fails with Google Cloud SDK Python runtime issues, set a compatible interpreter:

```bash
which python3
export CLOUDSDK_PYTHON=/path/to/python3
bq query --use_legacy_sql=false --dry_run --format=json 'SELECT 1'
```

Persist it in shell profile if needed:

```bash
echo 'export CLOUDSDK_PYTHON=/path/to/python3' >> ~/.zshrc
```

If uploaded CSV looks corrupted in Dekart (for example contains `Waiting on bqjob...`):

- Root cause is usually redirecting stderr into CSV.
- Never use `2>&1` when writing CSV files.

Use this export pattern:

```bash
bq query --use_legacy_sql=false --format=csv --maximum_bytes_billed=10737418240 --max_rows=100 'SELECT ...' > /tmp/result.csv 2>/tmp/result.stderr.log
wc -l /tmp/result.csv
```
