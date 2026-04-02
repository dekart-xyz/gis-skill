import argparse
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
SOURCE_SKILL_FILE = PACKAGE_ROOT / "SKILL.md"


def build_parser():
    """Build CLI parser for giskill commands."""
    parser = argparse.ArgumentParser(
        prog="giskill",
        description="Create maps and answer questions from your data."
    )
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser("install", help="Install integrations for supported CLIs.")
    install.add_argument("target", choices=["claude"], help="CLI target to install giskill into.")
    return parser


def install_claude_skill():
    """Install giskill into Claude skills directory."""
    skill_dir = Path.home() / ".claude" / "skills" / "giskill"
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    skill_file.write_text(SOURCE_SKILL_FILE.read_text(encoding="utf-8"), encoding="utf-8")

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

    parser.print_help()


if __name__ == "__main__":
    main()
