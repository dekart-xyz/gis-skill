import argparse
import shutil
import sys
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT_SKILL_FILE = PACKAGE_ROOT / "SKILL.md"
ROOT_REFERENCES_DIR = PACKAGE_ROOT / "references"


def build_parser():
    """Build CLI parser for geosql commands."""
    parser = argparse.ArgumentParser(
        prog="geosql",
        description="Install GeoSQL files into local AI toolchains.",
    )
    subparsers = parser.add_subparsers(dest="command")

    install = subparsers.add_parser("install", help="Install geosql into a supported CLI.")
    install.add_argument("target", choices=["claude"], help="CLI target to install geosql into.")

    return parser


def install_claude_skill():
    """Install geosql SKILL.md and references into Claude skills directory."""
    skill_dir = Path.home() / ".claude" / "skills" / "geosql"
    skill_dir.mkdir(parents=True, exist_ok=True)

    skill_file = skill_dir / "SKILL.md"
    if not ROOT_SKILL_FILE.exists():
        print(f"Missing skill source: {ROOT_SKILL_FILE}", file=sys.stderr)
        return 1

    skill_source = ROOT_SKILL_FILE.read_text(encoding="utf-8")
    skill_file.write_text(skill_source, encoding="utf-8")
    installed_references = 0

    if ROOT_REFERENCES_DIR.exists() and ROOT_REFERENCES_DIR.is_dir():
        target_references_dir = skill_dir / "references"
        if target_references_dir.exists():
            shutil.rmtree(target_references_dir)
        shutil.copytree(ROOT_REFERENCES_DIR, target_references_dir)
        installed_references = sum(1 for path in target_references_dir.rglob("*") if path.is_file())

    print(f"Installed Claude skill at {skill_file}")
    if installed_references:
        print(f"Installed references at {skill_dir / 'references'} ({installed_references} file(s))")
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
