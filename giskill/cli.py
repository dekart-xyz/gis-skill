import argparse
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT_SKILL_FILE = PACKAGE_ROOT / "SKILL.md"


def build_parser():
    """Build CLI parser for giskill commands."""
    parser = argparse.ArgumentParser(
        prog="giskill",
        description="Create maps and answer questions from your data.",
    )
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser("install", help="Install integrations for supported CLIs.")
    install.add_argument("target", choices=["claude"], help="CLI target to install giskill into.")

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


def main():
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "install":
        if args.target == "claude":
            raise SystemExit(install_claude_skill())
        parser.error(f"Unsupported install target: {args.target}")
        return

    parser.print_help()


if __name__ == "__main__":
    main()
