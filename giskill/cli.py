import argparse
import datetime as dt
import json
import mimetypes
import os
import platform
import tempfile
import time
import sys
import urllib.error
import urllib.request
import webbrowser
from urllib.parse import urlparse
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT_SKILL_FILE = PACKAGE_ROOT / "SKILL.md"
DEFAULT_DEKART_URL = "https://cloud.dekart.xyz"


def build_parser():
    """Build CLI parser for giskill commands."""
    parser = argparse.ArgumentParser(
        prog="giskill",
        description="Create maps and answer questions from your data.",
    )
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser("install", help="Install integrations for supported CLIs.")
    install.add_argument("target", choices=["claude"], help="CLI target to install giskill into.")

    dekart = subparsers.add_parser("dekart", help="Manage Dekart integration settings.")
    dekart_subparsers = dekart.add_subparsers(dest="dekart_command")
    dekart_config = dekart_subparsers.add_parser("config", help="Set or show Dekart base URL.")
    dekart_config.add_argument(
        "--url",
        help="Dekart base URL (examples: http://localhost:3000, https://my-dekart.company.com).",
    )
    dekart_init = dekart_subparsers.add_parser("init", help="Authorize this CLI against Dekart.")
    dekart_init.add_argument(
        "--no-browser",
        action="store_true",
        help="Print authorization URL without opening browser automatically.",
    )
    dekart_tools = dekart_subparsers.add_parser("tools", help="List MCP tools from configured Dekart.")
    dekart_tools.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON payload.",
    )
    dekart_resolve_tools = dekart_subparsers.add_parser(
        "resolve-tools",
        help="Resolve required Dekart MCP tool names for report->dataset->file flow.",
    )
    dekart_resolve_tools.add_argument(
        "--json",
        action="store_true",
        help="Print resolved mapping as JSON.",
    )
    dekart_resolve_tools.add_argument(
        "--shell",
        action="store_true",
        help="Print shell exports for eval/source usage.",
    )
    dekart_resolve_tools.add_argument(
        "--out",
        help="Write output to file path instead of stdout.",
    )
    dekart_call = dekart_subparsers.add_parser("call", help="Call Dekart MCP tool.")
    dekart_call.add_argument("--name", required=True, help="MCP tool name.")
    dekart_call.add_argument(
        "--args",
        default="{}",
        help="Tool arguments as JSON object string.",
    )
    dekart_call.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON payload.",
    )
    dekart_call.add_argument(
        "--extract",
        help="Extract one scalar field from full response JSON path, for example: result.report.id",
    )
    dekart_call.add_argument(
        "--out",
        help="Write command output to file path instead of stdout.",
    )
    dekart_upload = dekart_subparsers.add_parser(
        "upload-parts",
        help="Upload local file bytes with MCP-provided multipart part endpoint and headers.",
    )
    dekart_upload.add_argument("--file", required=True, help="Local file path to upload.")
    dekart_upload.add_argument(
        "--start-response-json",
        help="JSON string from start_file_upload_session (either full MCP response or result object).",
    )
    dekart_upload.add_argument(
        "--start-response-file",
        help="Path to JSON file from start_file_upload_session.",
    )
    dekart_upload.add_argument(
        "--upload-part-endpoint",
        help="Part endpoint template (for example /api/v1/file/.../parts/{part_number}).",
    )
    dekart_upload.add_argument(
        "--required-headers-json",
        help='JSON list with headers, for example \'[{"key":"x-header","value":"v"}]\'.',
    )
    dekart_upload.add_argument(
        "--max-part-size",
        type=int,
        help="Max bytes per part. If omitted, uses value from start response.",
    )
    dekart_upload.add_argument(
        "--file-id",
        help="File id override. Use when start response does not include file_id.",
    )
    dekart_upload.add_argument(
        "--complete-args-out",
        help="Write ready JSON args for complete_file_upload_session to this file path.",
    )
    dekart_upload.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON payload.",
    )
    dekart_upload_file = dekart_subparsers.add_parser(
        "upload-file",
        help="Start upload session, upload parts, and complete in one command.",
    )
    dekart_upload_file.add_argument("--file", required=True, help="Local file path to upload.")
    dekart_upload_file.add_argument("--file-id", required=True, help="Dekart file_id created via MCP create_file.")
    dekart_upload_file.add_argument(
        "--name",
        help="Uploaded file name metadata. Defaults to local file basename.",
    )
    dekart_upload_file.add_argument(
        "--mime-type",
        help="Uploaded file MIME type. Defaults to inferred type or application/octet-stream.",
    )
    dekart_upload_file.add_argument(
        "--max-part-size",
        type=int,
        help="Optional max part size override. If omitted, uses start response value.",
    )
    dekart_upload_file.add_argument(
        "--json",
        action="store_true",
        help="Print raw JSON payload.",
    )
    dekart_upload_file.add_argument(
        "--out",
        help="Write JSON payload to file path instead of stdout.",
    )

    return parser


def install_claude_skill():
    """Install giskill SKILL.md into Claude skills directory."""
    skill_dir = Path.home() / ".claude" / "skills" / "giskill"
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    if not ROOT_SKILL_FILE.exists():
        print(f"Missing skill source: {ROOT_SKILL_FILE}", file=sys.stderr)
        return 1

    skill_source = ROOT_SKILL_FILE.read_text(encoding="utf-8")
    skill_file.write_text(skill_source, encoding="utf-8")

    print(f"Installed Claude skill at {skill_file}")
    return 0


def get_config_path():
    """Return user config file path for giskill."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME", "").strip()
    config_root = Path(xdg_config_home) if xdg_config_home else (Path.home() / ".config")
    return config_root / "giskill" / "config.json"


def load_config(path):
    """Load JSON config from disk."""
    if not path.exists():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_config(path, data):
    """Persist JSON config to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def is_valid_http_url(url):
    """Return True when URL uses http/https and has a hostname."""
    parsed = urlparse(url)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def handle_dekart_config(url):
    """Set or show configured Dekart URL."""
    config_path = get_config_path()
    config = load_config(config_path)

    if url:
        normalized_url = url.rstrip("/")
        if not is_valid_http_url(normalized_url):
            print("Invalid URL. Use full http(s) URL, for example: http://localhost:3000", file=sys.stderr)
            return 2
        config["dekart_url"] = normalized_url
        save_config(config_path, config)
        print(f"Dekart URL saved: {normalized_url}")
        print(f"Config file: {config_path}")
        return 0

    configured_url = config.get("dekart_url", "").strip()
    effective_url = configured_url or DEFAULT_DEKART_URL
    source = "user_config" if configured_url else "default_cloud"
    print(f"Dekart URL: {effective_url}")
    print(f"Source: {source}")
    print(f"Config file: {config_path}")
    return 0


def get_dekart_url():
    """Resolve configured Dekart URL with cloud default fallback."""
    config_path = get_config_path()
    config = load_config(config_path)
    configured_url = config.get("dekart_url", "").strip()
    return configured_url or DEFAULT_DEKART_URL


def get_token_path():
    """Return token storage path for Dekart CLI auth."""
    config_path = get_config_path()
    return config_path.parent / "token.json"


def post_json(url, payload, timeout_seconds=15):
    """Send JSON POST request and return decoded JSON response."""
    request_body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url=url,
        data=request_body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
        if not body.strip():
            return {}
        return json.loads(body)


def read_json(url, headers=None, timeout_seconds=15):
    """Send JSON GET request and return decoded JSON response."""
    request = urllib.request.Request(
        url=url,
        headers=headers or {},
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
        if not body.strip():
            return {}
        return json.loads(body)


def save_token(token_path, dekart_url, token_payload):
    """Persist authorized Dekart token payload for future CLI operations."""
    expires_in = int(token_payload.get("expires_in", 0) or 0)
    now = dt.datetime.now(dt.timezone.utc)
    expires_at = now + dt.timedelta(seconds=expires_in) if expires_in > 0 else None
    payload = {
        "dekart_url": dekart_url,
        "token": token_payload.get("token", ""),
        "email": token_payload.get("email", ""),
        "workspace_id": token_payload.get("workspace_id", ""),
        "created_at": now.isoformat(),
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    token_path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2) + "\n"

    tmp_name = None
    try:
        fd, tmp_name = tempfile.mkstemp(prefix=f".{token_path.name}.", dir=str(token_path.parent))
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            # why: token is a bearer credential and must not be readable by other users.
            try:
                os.fchmod(tmp_file.fileno(), 0o600)
            except AttributeError:
                pass
            tmp_file.write(serialized)
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        os.replace(tmp_name, token_path)
        try:
            os.chmod(token_path, 0o600)
        except OSError:
            pass
    finally:
        if tmp_name and os.path.exists(tmp_name):
            os.unlink(tmp_name)


def load_token(token_path):
    """Load saved token payload for authenticated Dekart API requests."""
    if not token_path.exists():
        return {}
    try:
        payload = json.loads(token_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def get_auth_headers():
    """Build Authorization headers from locally saved device token."""
    token_path = get_token_path()
    payload = load_token(token_path)
    token = str(payload.get("token", "")).strip()
    if not token:
        return None
    return {"Authorization": f"Bearer {token}"}


def pretty_print_json(payload):
    """Print stable JSON for CLI output."""
    print(json.dumps(payload, indent=2, sort_keys=True))


def write_json_file(path, payload):
    """Write pretty JSON payload to file path."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_text_file(path, content):
    """Write plain text content to file path."""
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")


def extract_json_path(payload, json_path):
    """Extract value by dot-separated JSON path from payload."""
    path = str(json_path or "").strip()
    if not path:
        raise ValueError("Empty extract path.")
    if path.startswith("$."):
        path = path[2:]
    if path.startswith("$"):
        path = path[1:]
    if not path:
        raise ValueError("Empty extract path.")

    current = payload
    for segment in path.split("."):
        key = segment.strip()
        if not key:
            raise ValueError(f"Invalid extract path: {json_path}")
        if isinstance(current, dict):
            if key not in current:
                raise ValueError(f"Path not found: {json_path}")
            current = current[key]
            continue
        if isinstance(current, list):
            try:
                index = int(key)
            except ValueError as exc:
                raise ValueError(f"Expected numeric index in path segment `{key}`.") from exc
            if index < 0 or index >= len(current):
                raise ValueError(f"List index out of range in path segment `{key}`.")
            current = current[index]
            continue
        raise ValueError(f"Path segment `{key}` cannot be resolved on scalar value.")
    return current


def format_scalar(value):
    """Format scalar JSON value as plain text."""
    if isinstance(value, bool):
        return "true"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        return value
    raise ValueError("Extracted value is not scalar.")


def parse_int(value, default=0):
    """Convert protobuf/json numeric field to int with safe fallback."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def mcp_call(name, args, timeout_seconds=30):
    """Call one MCP tool and return parsed response payload."""
    dekart_url = get_dekart_url().rstrip("/")
    endpoint = f"{dekart_url}/api/v1/mcp/call"
    headers = {"Content-Type": "application/json"}
    auth_headers = get_auth_headers()
    if auth_headers:
        headers.update(auth_headers)

    request_body = json.dumps({"name": name, "arguments": args}).encode("utf-8")
    request = urllib.request.Request(url=endpoint, data=request_body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def parse_upload_start_payload(start_response_json, start_response_file):
    """Parse start_file_upload_session JSON and return normalized result object."""
    raw_payload = None
    if start_response_json:
        raw_payload = start_response_json
    elif start_response_file:
        try:
            raw_payload = Path(start_response_file).read_text(encoding="utf-8")
        except OSError as exc:
            raise ValueError(f"Failed to read --start-response-file: {exc}") from exc
    if raw_payload is None:
        return {}
    try:
        parsed = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid start response JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError("Start response JSON must be an object.")
    result = parsed.get("result")
    if isinstance(result, dict):
        return result
    return parsed


def upload_part_binary(put_url, body_bytes, required_headers):
    """Upload one multipart chunk to Dekart part endpoint and return JSON manifest item."""
    headers = {"Content-Type": "application/octet-stream", "Content-Length": str(len(body_bytes))}
    auth_headers = get_auth_headers()
    if auth_headers:
        headers.update(auth_headers)
    for item in required_headers or []:
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", ""))
        if key:
            headers[key] = value

    request = urllib.request.Request(url=put_url, data=body_bytes, headers=headers, method="PUT")
    with urllib.request.urlopen(request, timeout=120) as response:
        body = response.read().decode("utf-8")
        return json.loads(body) if body.strip() else {}


def parse_required_headers(required_headers_json):
    """Parse headers JSON into MCP-compatible key/value list."""
    if not required_headers_json:
        return []
    try:
        parsed = json.loads(required_headers_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid --required-headers-json: {exc}") from exc
    if not isinstance(parsed, list):
        raise ValueError("--required-headers-json must be a JSON array.")
    headers = []
    for item in parsed:
        if not isinstance(item, dict):
            raise ValueError("--required-headers-json items must be objects with key/value.")
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", ""))
        if key:
            headers.append({"key": key, "value": value})
    return headers


def build_put_url(dekart_url, endpoint_template, part_number, part_size):
    """Build part upload URL from endpoint template and current part metadata."""
    if "{part_number}" not in endpoint_template:
        raise ValueError("upload_part_endpoint must include {part_number}.")
    endpoint = endpoint_template.replace("{part_number}", str(part_number))
    base_url = endpoint if endpoint.startswith("http://") or endpoint.startswith("https://") else f"{dekart_url}{endpoint}"
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}part_size={part_size}"


def upload_parts_from_start_result(local_file, start_result, upload_part_endpoint, required_headers_json, max_part_size, file_id):
    """Upload local file bytes using one upload session result payload."""
    file_size = local_file.stat().st_size
    resolved_endpoint = (upload_part_endpoint or str(start_result.get("upload_part_endpoint", ""))).strip()
    if not resolved_endpoint:
        raise ValueError("Missing upload part endpoint. Provide --upload-part-endpoint or start response JSON/file.")
    resolved_max_part_size = max_part_size if max_part_size and max_part_size > 0 else parse_int(start_result.get("max_part_size"), 0)
    if resolved_max_part_size <= 0:
        raise ValueError("Missing max part size. Provide --max-part-size or start response JSON/file.")
    if required_headers_json:
        required_headers = parse_required_headers(required_headers_json)
    else:
        required_headers = start_result.get("required_headers", [])
        if not isinstance(required_headers, list):
            required_headers = []
    upload_session_id = str(start_result.get("upload_session_id", "")).strip()
    start_file_id = str(start_result.get("file_id", "")).strip()
    resolved_file_id = str(file_id or "").strip() or start_file_id
    if not resolved_file_id:
        raise ValueError("Missing file id. Provide --file-id or include file_id in start response.")
    if not upload_session_id:
        raise ValueError("Missing upload_session_id in start response.")
    dekart_url = get_dekart_url().rstrip("/")

    parts = []
    part_number = 1
    with local_file.open("rb") as source:
        while True:
            chunk = source.read(resolved_max_part_size)
            if not chunk:
                break
            put_url = build_put_url(dekart_url, resolved_endpoint, part_number, len(chunk))
            part_response = upload_part_binary(put_url, chunk, required_headers)
            parts.append(
                {
                    "part_number": parse_int(part_response.get("part_number"), part_number),
                    "etag": str(part_response.get("etag", "")),
                    "size": parse_int(part_response.get("size"), len(chunk)),
                }
            )
            part_number += 1

    complete_args = {
        "file_id": resolved_file_id,
        "upload_session_id": upload_session_id,
        "parts": parts,
        "total_size": file_size,
    }
    return {
        "parts": parts,
        "parts_uploaded": len(parts),
        "total_size": file_size,
        "max_part_size": resolved_max_part_size,
        "upload_session_id": upload_session_id,
        "file_id": resolved_file_id,
        "complete_args": complete_args,
    }


def handle_dekart_tools(raw_json):
    """Fetch MCP tool catalog from configured Dekart instance."""
    try:
        payload = fetch_mcp_tools_payload()
    except urllib.error.HTTPError as exc:
        print(f"MCP tools request failed ({exc.code}): {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"MCP tools request failed: {exc}", file=sys.stderr)
        return 1

    if raw_json:
        pretty_print_json(payload)
        return 0

    tools = payload.get("tools", [])
    if not isinstance(tools, list):
        print("Invalid MCP tools response.", file=sys.stderr)
        return 1
    print(f"MCP tools: {len(tools)}")
    for item in tools:
        name = str(item.get("name", "")).strip()
        description = str(item.get("description", "")).strip()
        if name:
            if description:
                print(f"- {name}: {description}")
            else:
                print(f"- {name}")
    return 0


def fetch_mcp_tools_payload():
    """Fetch MCP tool catalog payload from configured Dekart instance."""
    dekart_url = get_dekart_url().rstrip("/")
    endpoint = f"{dekart_url}/api/v1/mcp/tools"
    headers = get_auth_headers()
    return read_json(endpoint, headers=headers)


def tool_required_fields(tool):
    """Return required input schema fields for one MCP tool definition."""
    schema = tool.get("inputSchema", {}) if isinstance(tool, dict) else {}
    required = schema.get("required", []) if isinstance(schema, dict) else []
    return set(required) if isinstance(required, list) else set()


def tool_properties(tool):
    """Return declared input schema properties for one MCP tool definition."""
    schema = tool.get("inputSchema", {}) if isinstance(tool, dict) else {}
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}
    return set(props.keys()) if isinstance(props, dict) else set()


def pick_mcp_tool_name(tools, required_fields=(), required_props=(), preferred_names=(), name_contains=()):
    """Resolve one MCP tool name by schema constraints and optional preferred names."""
    required_fields = set(required_fields)
    required_props = set(required_props)
    name_contains = tuple(str(token).lower() for token in name_contains)

    def collect(filter_by_name):
        matches = []
        for tool in tools:
            name = str(tool.get("name", "")).strip()
            if not name:
                continue
            req = tool_required_fields(tool)
            props = tool_properties(tool)
            if not required_fields.issubset(req) or not required_props.issubset(props):
                continue
            if filter_by_name:
                lowered = name.lower()
                if not all(token in lowered for token in name_contains):
                    continue
            matches.append(name)
        return matches

    candidates = collect(filter_by_name=bool(name_contains))
    if not candidates and name_contains:
        candidates = collect(filter_by_name=False)

    for preferred in preferred_names:
        if preferred in candidates:
            return preferred
    return candidates[0] if candidates else ""


def resolve_dekart_tool_mapping(tools):
    """Resolve canonical report->dataset->file tool mapping from MCP tool list."""
    mapping = {
        "create_report_tool": pick_mcp_tool_name(
            tools,
            required_fields=(),
            required_props=(),
            preferred_names=("create_report",),
            name_contains=("report",),
        ),
        "create_dataset_tool": pick_mcp_tool_name(
            tools,
            required_fields=("report_id",),
            required_props=("report_id",),
            preferred_names=("create_dataset",),
            name_contains=("dataset",),
        ),
        "create_file_tool": pick_mcp_tool_name(
            tools,
            required_fields=("dataset_id",),
            required_props=("dataset_id",),
            preferred_names=("create_file",),
            name_contains=("file",),
        ),
    }
    missing = [key for key, value in mapping.items() if not str(value).strip()]
    if missing:
        raise ValueError(f"Missing required MCP tools for workflow: {', '.join(missing)}")
    return mapping


def render_shell_exports(mapping):
    """Render mapping as shell export lines safe for eval/source."""
    lines = []
    for key, value in mapping.items():
        env_key = key.upper()
        lines.append(f"export {env_key}={json.dumps(value)}")
    return "\n".join(lines) + "\n"


def handle_dekart_resolve_tools(raw_json, shell, out):
    """Resolve required MCP tool names and print as JSON or shell exports."""
    if raw_json and shell:
        print("Use either --json or --shell, not both.", file=sys.stderr)
        return 2
    try:
        payload = fetch_mcp_tools_payload()
        tools = payload.get("tools", [])
        if not isinstance(tools, list):
            print("Invalid MCP tools response.", file=sys.stderr)
            return 1
        mapping = resolve_dekart_tool_mapping(tools)
    except ValueError as exc:
        print(f"Tool resolution failed: {exc}", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as exc:
        print(f"MCP tools request failed ({exc.code}): {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"MCP tools request failed: {exc}", file=sys.stderr)
        return 1

    try:
        if shell:
            shell_text = render_shell_exports(mapping)
            if out:
                write_text_file(out, shell_text)
            else:
                print(shell_text, end="")
            return 0
        if raw_json:
            if out:
                write_json_file(out, mapping)
            else:
                pretty_print_json(mapping)
            return 0
        lines = [f"{key}: {value}" for key, value in mapping.items()]
        text = "\n".join(lines) + "\n"
        if out:
            write_text_file(out, text)
        else:
            print(text, end="")
        return 0
    except OSError as exc:
        print(f"Failed to write output file: {exc}", file=sys.stderr)
        return 1


def handle_dekart_call(name, args_json, raw_json, extract, out):
    """Call one MCP tool using dynamic tool name and JSON arguments."""
    try:
        parsed_args = json.loads(args_json)
    except json.JSONDecodeError as exc:
        print(f"Invalid --args JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(parsed_args, dict):
        print("Invalid --args JSON: must be an object.", file=sys.stderr)
        return 2

    try:
        payload = mcp_call(name, parsed_args, timeout_seconds=30)
    except urllib.error.HTTPError as exc:
        print(f"MCP call failed ({exc.code}): {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"MCP call failed: {exc}", file=sys.stderr)
        return 1

    try:
        if extract:
            value = extract_json_path(payload, extract)
            scalar = format_scalar(value)
            if out:
                write_text_file(out, scalar + "\n")
            else:
                print(scalar)
            return 0

        output_payload = payload if raw_json else payload.get("result", {})
        if out:
            write_json_file(out, output_payload)
        else:
            pretty_print_json(output_payload)
        return 0
    except ValueError as exc:
        print(f"Invalid extract/output request: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Failed to write output file: {exc}", file=sys.stderr)
        return 1


def handle_dekart_upload_parts(
    file_path,
    start_response_json,
    start_response_file,
    upload_part_endpoint,
    required_headers_json,
    max_part_size,
    file_id,
    complete_args_out,
    raw_json,
):
    """Upload local file chunks using start session metadata prepared by MCP."""
    local_file = Path(file_path)
    if not local_file.exists() or not local_file.is_file():
        print(f"File not found: {local_file}", file=sys.stderr)
        return 2
    file_size = local_file.stat().st_size
    if file_size <= 0:
        print("File is empty.", file=sys.stderr)
        return 2

    try:
        start_result = parse_upload_start_payload(start_response_json, start_response_file)
        payload = upload_parts_from_start_result(
            local_file=local_file,
            start_result=start_result,
            upload_part_endpoint=upload_part_endpoint,
            required_headers_json=required_headers_json,
            max_part_size=max_part_size,
            file_id=file_id,
        )
        if complete_args_out:
            write_json_file(complete_args_out, payload.get("complete_args", {}))
        if raw_json:
            pretty_print_json(payload)
        else:
            print(f"Uploaded parts: {payload.get('parts_uploaded', 0)}")
            print(f"Total size: {payload.get('total_size', file_size)} bytes")
            pretty_print_json(payload.get("complete_args", {}))
        return 0
    except ValueError as exc:
        print(f"Invalid upload arguments: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Failed to write output file: {exc}", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as exc:
        print(f"Upload part request failed ({exc.code}): {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Upload failed: {exc}", file=sys.stderr)
        return 1


def resolve_upload_file_name(local_file, explicit_name):
    """Resolve uploaded file name from explicit value or local file basename."""
    name = str(explicit_name or "").strip()
    if name:
        return name
    return local_file.name


def resolve_upload_mime_type(local_file, explicit_mime_type):
    """Resolve MIME type from explicit value or local file extension."""
    mime_type = str(explicit_mime_type or "").strip()
    if mime_type:
        return mime_type
    guessed, _ = mimetypes.guess_type(str(local_file))
    return guessed or "application/octet-stream"


def handle_dekart_upload_file(file_path, file_id, name, mime_type, max_part_size, raw_json, out):
    """Upload one file end-to-end using MCP start/complete and CLI part PUT automation."""
    local_file = Path(file_path)
    if not local_file.exists() or not local_file.is_file():
        print(f"File not found: {local_file}", file=sys.stderr)
        return 2
    total_size = local_file.stat().st_size
    if total_size <= 0:
        print("File is empty.", file=sys.stderr)
        return 2

    try:
        start_args = {
            "file_id": str(file_id).strip(),
            "name": resolve_upload_file_name(local_file, name),
            "mime_type": resolve_upload_mime_type(local_file, mime_type),
            "total_size": total_size,
        }
        start_payload = mcp_call("start_file_upload_session", start_args, timeout_seconds=30)
        start_result = start_payload.get("result", {}) if isinstance(start_payload, dict) else {}
        if not isinstance(start_result, dict):
            raise ValueError("Invalid start_file_upload_session response.")

        upload_payload = upload_parts_from_start_result(
            local_file=local_file,
            start_result=start_result,
            upload_part_endpoint="",
            required_headers_json="",
            max_part_size=max_part_size,
            file_id=file_id,
        )
        complete_args = upload_payload.get("complete_args", {})
        complete_payload = mcp_call("complete_file_upload_session", complete_args, timeout_seconds=60)
        complete_result = complete_payload.get("result", complete_payload) if isinstance(complete_payload, dict) else complete_payload

        payload = {
            "start": start_result,
            "upload": upload_payload,
            "complete": complete_result,
        }
        if out:
            write_json_file(out, payload)
        if raw_json:
            pretty_print_json(payload)
        elif not out:
            print(f"Uploaded parts: {upload_payload.get('parts_uploaded', 0)}")
            print(f"Total size: {upload_payload.get('total_size', total_size)} bytes")
            pretty_print_json(complete_result)
        return 0
    except ValueError as exc:
        print(f"Invalid upload-file arguments: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Failed to write output file: {exc}", file=sys.stderr)
        return 1
    except urllib.error.HTTPError as exc:
        print(f"Upload-file request failed ({exc.code}): {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Upload-file failed: {exc}", file=sys.stderr)
        return 1


# build_device_name returns concise local machine label for Dekart device session records.
def build_device_name():
    """Build local device label for Dekart authorization records."""
    node_name = platform.node().strip() or "unknown-host"
    system_name = platform.system().strip() or "UnknownOS"
    return f"{node_name} ({system_name})"


def handle_dekart_init(no_browser):
    """Run device authorization flow and save returned Dekart CLI token."""
    dekart_url = get_dekart_url().rstrip("/")
    device_endpoint = f"{dekart_url}/api/v1/device"
    token_endpoint = f"{dekart_url}/api/v1/device/token"
    token_path = get_token_path()

    try:
        start_payload = post_json(device_endpoint, {"device_name": build_device_name()})
    except urllib.error.HTTPError as exc:
        print(f"Device registration failed ({exc.code}): {exc.reason}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Device registration failed: {exc}", file=sys.stderr)
        return 1

    device_id = str(start_payload.get("device_id", "")).strip()
    auth_url = str(start_payload.get("auth_url", "")).strip()
    expires_in = int(start_payload.get("expires_in", 0) or 0)
    interval = int(start_payload.get("interval", 3) or 3)
    interval = max(interval, 1)

    if not device_id or not auth_url or expires_in <= 0:
        print("Invalid response from Dekart device endpoint.", file=sys.stderr)
        return 1

    print("Opening browser to authorize...")
    print(f"Auth URL: {auth_url}")
    if not no_browser:
        try:
            webbrowser.open(auth_url, new=2, autoraise=True)
        except Exception:
            print("Could not open browser automatically. Open the URL manually.", file=sys.stderr)

    print("Waiting for authorization...")
    deadline = time.monotonic() + expires_in
    while time.monotonic() <= deadline:
        try:
            token_payload = post_json(token_endpoint, {"device_id": device_id}, timeout_seconds=max(interval + 5, 10))
        except urllib.error.HTTPError as exc:
            print(f"Token polling failed ({exc.code}): {exc.reason}", file=sys.stderr)
            return 1
        except Exception as exc:
            print(f"Token polling failed: {exc}", file=sys.stderr)
            return 1

        status = str(token_payload.get("status", "")).strip()
        if status == "authorized" and token_payload.get("token"):
            save_token(token_path, dekart_url, token_payload)
            email = token_payload.get("email", "")
            print(f"Done. Authenticated as {email}")
            print(f"Token saved: {token_path}")
            return 0
        if status == "expired":
            print("Authorization expired. Run giskill dekart init again.", file=sys.stderr)
            return 1
        if status not in {"pending", ""}:
            error = token_payload.get("error", "unknown_error")
            print(f"Authorization failed: {error}", file=sys.stderr)
            return 1

        time.sleep(interval)

    print("Authorization timed out. Run giskill dekart init again.", file=sys.stderr)
    return 1


def main():
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "install":
        if args.target == "claude":
            raise SystemExit(install_claude_skill())
        parser.error(f"Unsupported install target: {args.target}")
        return

    if args.command == "dekart":
        if args.dekart_command == "config":
            raise SystemExit(handle_dekart_config(args.url))
        if args.dekart_command == "init":
            raise SystemExit(handle_dekart_init(args.no_browser))
        if args.dekart_command == "tools":
            raise SystemExit(handle_dekart_tools(args.json))
        if args.dekart_command == "resolve-tools":
            raise SystemExit(handle_dekart_resolve_tools(args.json, args.shell, args.out))
        if args.dekart_command == "call":
            raise SystemExit(handle_dekart_call(args.name, args.args, args.json, args.extract, args.out))
        if args.dekart_command == "upload-parts":
            raise SystemExit(
                handle_dekart_upload_parts(
                    file_path=args.file,
                    start_response_json=args.start_response_json,
                    start_response_file=args.start_response_file,
                    upload_part_endpoint=args.upload_part_endpoint,
                    required_headers_json=args.required_headers_json,
                    max_part_size=args.max_part_size,
                    file_id=args.file_id,
                    complete_args_out=args.complete_args_out,
                    raw_json=args.json,
                )
            )
        if args.dekart_command == "upload-file":
            raise SystemExit(
                handle_dekart_upload_file(
                    file_path=args.file,
                    file_id=args.file_id,
                    name=args.name,
                    mime_type=args.mime_type,
                    max_part_size=args.max_part_size,
                    raw_json=args.json,
                    out=args.out,
                )
            )
        parser.error("Missing dekart subcommand. Try: giskill dekart config --url <url>")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
