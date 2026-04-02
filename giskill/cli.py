import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT_SKILL_FILE = PACKAGE_ROOT / "SKILL.md"
DEFAULT_MAX_BYTES = 10737418240


def resolve_source_skill_file():
    """Return canonical SKILL.md source path."""
    return ROOT_SKILL_FILE


def add_query_args(parser):
    """Attach shared query command arguments to a parser."""
    parser.add_argument("--mode", choices=["sql_only", "execute"], default="sql_only")
    parser.add_argument("--query", help="SQL text")
    parser.add_argument("--query-file", help="File containing SQL")
    parser.add_argument("--project-id", help="Override project")
    parser.add_argument("--location", help="Override location")
    parser.add_argument("--max-bytes", type=int, help="Override maximum_bytes_billed")
    parser.add_argument("--allow-over-budget", action="store_true", help="Allow execute above budget")
    parser.add_argument("--result-max-rows", type=int, default=20, help="Preview row count for execute")


def build_parser():
    """Build CLI parser for giskill commands."""
    parser = argparse.ArgumentParser(
        prog="giskill",
        description="Create maps and answer questions from your data.",
    )
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser("install", help="Install integrations for supported CLIs.")
    install.add_argument("target", choices=["claude"], help="CLI target to install giskill into.")

    run = subparsers.add_parser(
        "run-cost-checked-query",
        help="Run BigQuery SQL with mandatory dry-run cost checks.",
    )
    add_query_args(run)

    query_alias = subparsers.add_parser(
        "query",
        help="Alias for run-cost-checked-query.",
    )
    add_query_args(query_alias)

    return parser


def load_dotenv_from_cwd():
    """Load .env from current directory into process environment if present."""
    env_path = Path.cwd() / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        os.environ.setdefault(key, value)


def resolve_project_id(override):
    """Resolve BigQuery project id from args, env, or gcloud config."""
    if override:
        return override

    from_env = os.environ.get("BQ_PROJECT_ID", "").strip()
    if from_env:
        return from_env

    gcloud_path = shutil.which("gcloud")
    if not gcloud_path:
        return ""

    proc = subprocess.run(
        [gcloud_path, "config", "get-value", "project"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return ""

    value = proc.stdout.strip().replace("\r", "")
    if value == "(unset)":
        return ""
    return value


def resolve_location(override):
    """Resolve BigQuery location from args or env."""
    if override:
        return override
    return os.environ.get("BQ_LOCATION", "").strip()


def resolve_max_bytes(override):
    """Resolve bytes budget from args, env, or default."""
    if override is not None:
        return int(override)

    from_env = os.environ.get("BQ_MAX_BYTES_BILLED", "").strip()
    if not from_env:
        return DEFAULT_MAX_BYTES

    try:
        return int(from_env)
    except ValueError:
        return DEFAULT_MAX_BYTES


def ensure_bq_credentials_file():
    """Materialize credentials file from BIGQUERY_CREDENTIALS_BASE64 if needed."""
    encoded = os.environ.get("BIGQUERY_CREDENTIALS_BASE64", "").strip()
    existing = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if not encoded or existing:
        return None

    tmp_dir = Path.cwd() / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    creds_path = tmp_dir / "bq-creds.json"
    creds_path.write_bytes(base64.b64decode(encoded))
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds_path)
    return creds_path


def emit_result(payload):
    """Print final JSON payload."""
    print(json.dumps(payload, ensure_ascii=True, indent=2))


def fail_json(mode, project_id, location, estimated_bytes, max_bytes, query_sql, message, next_steps):
    """Emit structured failure payload and return non-zero status code."""
    emit_result(
        {
            "mode": mode,
            "status": "dry_run_only",
            "project_id": project_id or None,
            "location": location or None,
            "estimated_bytes": int(estimated_bytes or 0),
            "max_bytes_billed": int(max_bytes or 0),
            "query_sql": query_sql,
            "result_preview": None,
            "next_steps": next_steps,
            "error": message,
        }
    )
    return 1


def read_query_input(query, query_file):
    """Resolve SQL input from text or file."""
    if query_file:
        path = Path(query_file)
        if not path.exists():
            raise FileNotFoundError(f"--query-file not found: {query_file}")
        return path.read_text(encoding="utf-8")
    return query or ""


def parse_dry_run_bytes(dry_run_output):
    """Extract estimated bytes from bq dry-run output."""
    data = json.loads(dry_run_output)
    if isinstance(data, list):
        item = data[0] if data else {}
    else:
        item = data
    query_stats = item.get("statistics", {}).get("query", {})
    return int(query_stats.get("totalBytesProcessed", 0))


def run_bq_query(query_sql, project_id, location, max_bytes, dry_run, max_rows):
    """Execute bq query command and return completed process."""
    bq_path = shutil.which("bq")
    if not bq_path:
        raise FileNotFoundError("bq")

    args = [
        bq_path,
        "query",
        "--use_legacy_sql=false",
        "--format=json",
        f"--project_id={project_id}",
        f"--maximum_bytes_billed={max_bytes}",
    ]
    if location:
        args.append(f"--location={location}")
    if dry_run:
        args.append("--dry_run")
    else:
        args.append(f"--max_rows={max_rows}")
    args.append(query_sql)

    return subprocess.run(args, capture_output=True, text=True, check=False)


def normalize_error(stderr):
    """Format subprocess stderr into one line for payload output."""
    return " ".join(stderr.splitlines()).strip()


def run_cost_checked_query(args):
    """Run cost-checked BigQuery query flow and emit structured JSON."""
    load_dotenv_from_cwd()

    try:
        query_sql = read_query_input(args.query, args.query_file)
    except FileNotFoundError as err:
        print(str(err), file=sys.stderr)
        return 2

    if not query_sql:
        print("Provide SQL with --query or --query-file", file=sys.stderr)
        return 2

    project_id = resolve_project_id(args.project_id)
    location = resolve_location(args.location)
    max_bytes = resolve_max_bytes(args.max_bytes)
    estimated_bytes = 0

    if not project_id:
        return fail_json(
            args.mode,
            project_id,
            location,
            estimated_bytes,
            max_bytes,
            query_sql,
            "Project could not be resolved.",
            ["Set BQ_PROJECT_ID or run: gcloud config set project <PROJECT_ID>"],
        )

    try:
        ensure_bq_credentials_file()
    except Exception as err:
        return fail_json(
            args.mode,
            project_id,
            location,
            estimated_bytes,
            max_bytes,
            query_sql,
            f"Credentials decode failed: {err}",
            ["Set BIGQUERY_CREDENTIALS_BASE64 to valid base64 JSON or use GOOGLE_APPLICATION_CREDENTIALS."],
        )

    if not shutil.which("bq"):
        return fail_json(
            args.mode,
            project_id,
            location,
            estimated_bytes,
            max_bytes,
            query_sql,
            "bq CLI is not available.",
            [
                "Install Google Cloud SDK and bq CLI, then authenticate before rerunning.",
                "macOS example: brew install --cask google-cloud-sdk",
            ],
        )

    dry = run_bq_query(
        query_sql=query_sql,
        project_id=project_id,
        location=location,
        max_bytes=max_bytes,
        dry_run=True,
        max_rows=args.result_max_rows,
    )
    if dry.returncode != 0:
        return fail_json(
            args.mode,
            project_id,
            location,
            estimated_bytes,
            max_bytes,
            query_sql,
            f"Dry run failed: {normalize_error(dry.stderr)}",
            ["Validate SQL syntax and dataset/table names.", "Verify auth with: gcloud auth application-default login"],
        )

    try:
        estimated_bytes = parse_dry_run_bytes(dry.stdout)
    except Exception as err:
        return fail_json(
            args.mode,
            project_id,
            location,
            estimated_bytes,
            max_bytes,
            query_sql,
            f"Could not parse dry run output: {err}",
            ["Re-run with --mode sql_only and inspect bq output format."],
        )

    status = "dry_run_only"
    result_preview = None
    next_steps = [
        "Review query_sql and validate required columns and filters.",
        "If needed, tighten bbox/date filters or reduce selected columns.",
    ]

    if args.mode == "execute":
        if (not args.allow_over_budget) and estimated_bytes > max_bytes:
            status = "blocked_over_budget"
            next_steps = [
                "Query blocked because dry-run estimate exceeds max_bytes_billed.",
                "Try tighter bbox/date filters, fewer columns, or pre-aggregation before geometry joins.",
            ]
        else:
            run = run_bq_query(
                query_sql=query_sql,
                project_id=project_id,
                location=location,
                max_bytes=max_bytes,
                dry_run=False,
                max_rows=args.result_max_rows,
            )
            if run.returncode != 0:
                return fail_json(
                    args.mode,
                    project_id,
                    location,
                    estimated_bytes,
                    max_bytes,
                    query_sql,
                    f"Execution failed: {normalize_error(run.stderr)}",
                    ["Check SQL and permissions.", "Retry after narrowing filters or lowering output cardinality."],
                )

            try:
                result_preview = json.loads(run.stdout)
            except json.JSONDecodeError:
                result_preview = run.stdout

            status = "executed"
            next_steps = [
                "Review result_preview and iterate query predicates if needed.",
                "Refine filters or selected fields if results are broader than intended.",
            ]

    emit_result(
        {
            "mode": args.mode,
            "status": status,
            "project_id": project_id,
            "location": location or None,
            "estimated_bytes": estimated_bytes,
            "max_bytes_billed": max_bytes,
            "query_sql": query_sql,
            "result_preview": result_preview,
            "next_steps": next_steps,
        }
    )
    return 0


def install_claude_skill():
    """Install giskill files into Claude skills directory."""
    skill_dir = Path.home() / ".claude" / "skills" / "giskill"
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    source_skill_file = resolve_source_skill_file()
    if not source_skill_file.exists():
        raise FileNotFoundError(f"Missing skill source: {source_skill_file}")
    skill_file.write_text(source_skill_file.read_text(encoding="utf-8"), encoding="utf-8")

    stale_script = skill_dir / "scripts" / "run_cost_checked_query.sh"
    if stale_script.exists():
        stale_script.unlink()
    stale_scripts_dir = skill_dir / "scripts"
    if stale_scripts_dir.exists() and not any(stale_scripts_dir.iterdir()):
        stale_scripts_dir.rmdir()

    print(f"Installed Claude skill at {skill_file}")


def main():
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "install":
        if args.target == "claude":
            install_claude_skill()
            return
        parser.error(f"Unsupported install target: {args.target}")
        return

    if args.command in {"run-cost-checked-query", "query"}:
        raise SystemExit(run_cost_checked_query(args))

    parser.print_help()


if __name__ == "__main__":
    main()
