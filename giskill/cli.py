import argparse
import json
import os
import sys
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
        parser.error("Missing dekart subcommand. Try: giskill dekart config --url <url>")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
