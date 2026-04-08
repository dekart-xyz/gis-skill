import argparse
import datetime as dt
import json
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

    return parser


def install_claude_skill():
    """Install giskill SKILL.md into Claude skills directory."""
    skill_dir = Path.home() / ".claude" / "skills" / "giskill"
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    if not ROOT_SKILL_FILE.exists():
        print(f"Missing skill source: {ROOT_SKILL_FILE}", file=sys.stderr)
        return 1
    skill_file.write_text(ROOT_SKILL_FILE.read_text(encoding="utf-8"), encoding="utf-8")

    # Clean up stale artifacts from older versions
    stale_script = skill_dir / "scripts" / "run_cost_checked_query.sh"
    if stale_script.exists():
        stale_script.unlink()
    stale_scripts_dir = skill_dir / "scripts"
    if stale_scripts_dir.exists() and not any(stale_scripts_dir.iterdir()):
        stale_scripts_dir.rmdir()

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
        parser.error("Missing dekart subcommand. Try: giskill dekart config --url <url>")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
