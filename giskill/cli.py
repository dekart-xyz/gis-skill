import argparse
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT_SKILL_FILE = PACKAGE_ROOT / "SKILL.md"


def build_parser():
    """Build CLI parser for giskill commands."""
    parser = argparse.ArgumentParser(
        prog="giskill",
        description="Install GIS skill files into local AI toolchains.",
    )
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser("install", help="Install giskill into a supported CLI.")
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

    skill_source = ROOT_SKILL_FILE.read_text(encoding="utf-8")
    skill_file.write_text(skill_source, encoding="utf-8")

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
