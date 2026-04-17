# gis-skill
Create maps and answer questions from your data.

## Install Claude skill

```bash
giskill install claude
```

This installs to:

`~/.claude/skills/giskill/SKILL.md`

During install, `giskill` resolves a working `bq` binary and writes it into the rendered skill file.

It does not auto-write detected `bq` path to config.

Optional override:

- Set `GISKILL_BQ_PATH` environment variable, or
- Set `bq_path` in `~/.config/giskill/config.json`

If no working `bq` is found, install fails fast so the skill is not installed in a broken state.

## Local Claude skill source

Canonical skill instructions are in:

`giskill/SKILL.md`

## How it works

Once installed, Claude Code auto-discovers the skill and uses it to build cost-safe Overture Maps SQL for BigQuery. During install, `giskill` renders SKILL template placeholder `{bq_path}` to a currently working local `bq` binary path.

Requires: [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) with `bq` CLI authenticated.

The rendered skill then calls `"{bq_path}" query ...` directly, without PATH-dependent prefixes.

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
