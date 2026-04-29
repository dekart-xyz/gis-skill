import argparse
import os
import select
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
    install.add_argument("target", choices=["claude", "codex", "all"], help="CLI target to install geosql into.")

    return parser


def is_interactive_terminal():
    """Return True when stdin/stdout are interactive terminals."""
    return bool(sys.stdin.isatty() and sys.stdout.isatty())


def supports_ansi_colors():
    """Return True when terminal likely supports ANSI colors."""
    if not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR"):
        return False
    term = os.environ.get("TERM", "").strip().lower()
    return term not in {"", "dumb"}


def ansi_rgb(text, red, green, blue, bold=False):
    """Wrap text with ANSI 24-bit color if available."""
    if not supports_ansi_colors():
        return text
    style = "1;" if bold else ""
    return f"\033[{style}38;2;{red};{green};{blue}m{text}\033[0m"


def print_banner():
    """Print GeoSQL startup banner."""
    lines = [
        "  ____            ____   ___  _     ",
        " / ___| ___  ___ / ___| / _ \\| |    ",
        "| |  _ / _ \\/ _ \\\\___ \\| | | | |    ",
        "| |_| |  __/ (_) |___) | |_| | |___ ",
        " \\____|\\___|\\___/|____/ \\__\\_\\_____|",
    ]
    title_color = (140, 210, 245)
    for line in lines:
        print(ansi_rgb(line, title_color[0], title_color[1], title_color[2], bold=True))
    print(ansi_rgb("GeoSQL installer", 235, 235, 235, bold=True))
    print()


def read_menu_key():
    """Read one key press for interactive menu selection."""
    if os.name == "nt":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in {"\r", "\n"}:
            return "enter"
        if ch in {"\x00", "\xe0"}:
            ch2 = msvcrt.getwch()
            if ch2 == "H":
                return "up"
            if ch2 == "P":
                return "down"
            return ""
        if ch in {"k", "K"}:
            return "up"
        if ch in {"j", "J"}:
            return "down"
        return ""

    import termios
    import tty

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = os.read(fd, 1)
        if ch == b"\x03":
            raise KeyboardInterrupt
        if ch in {b"\r", b"\n"}:
            return "enter"
        if ch in {b"k", b"K"}:
            return "up"
        if ch in {b"j", b"J"}:
            return "down"
        if ch == b"\x1b":
            ready, _, _ = select.select([sys.stdin], [], [], 0.03)
            if not ready:
                return "cancel"
            seq = os.read(fd, 2)
            if seq == b"[A":
                return "up"
            if seq == b"[B":
                return "down"
            return ""
        return ""
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def select_menu_option(title, options, default_index=0):
    """Render arrow-key menu and return selected index."""
    if not is_interactive_terminal() or not supports_ansi_colors() or not options:
        return None
    selected = max(0, min(int(default_index), len(options) - 1))
    cancelled = False

    def format_line(index):
        prefix = ">" if index == selected else " "
        line = f"  {prefix} {options[index]}"
        if index == selected:
            return ansi_rgb(line, 112, 181, 208, bold=True)
        return line

    try:
        print(ansi_rgb(title, 112, 181, 208, bold=True))
        print("Use ↑/↓ (or j/k) and Enter.")
        print()
        for idx in range(len(options)):
            print(format_line(idx))
        sys.stdout.write("\033[?25l")
        sys.stdout.flush()
        while True:
            key = read_menu_key()
            previous = selected
            if key == "up":
                selected = (selected - 1) % len(options)
            elif key == "down":
                selected = (selected + 1) % len(options)
            elif key == "enter":
                break
            elif key == "cancel":
                cancelled = True
                break

            if selected != previous:
                sys.stdout.write(f"\033[{len(options)}F")
                for idx in range(len(options)):
                    sys.stdout.write("\033[2K\r" + format_line(idx) + "\n")
                sys.stdout.flush()
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
    print()
    if cancelled:
        return "cancel"
    return selected


def install_skill_at(skill_dir, label):
    """Install geosql SKILL.md and references into a target skill directory."""
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

    print(f"Installed {label} skill at {skill_file}")
    if installed_references:
        print(f"Installed references at {skill_dir / 'references'} ({installed_references} file(s))")
    return 0


def install_claude_skill():
    """Install geosql files into Claude skill directory."""
    return install_skill_at(Path.home() / ".claude" / "skills" / "geosql", "Claude")


def install_codex_skill():
    """Install geosql files into Codex skill directory."""
    return install_skill_at(Path.home() / ".codex" / "skills" / "geosql", "Codex")


def detect_installed_agents():
    """Detect available agents and return ordered list of target ids."""
    detected = []
    claude_present = shutil.which("claude") is not None or (Path.home() / ".claude").exists()
    codex_present = shutil.which("codex") is not None or (Path.home() / ".codex").exists()
    if claude_present:
        detected.append("claude")
    if codex_present:
        detected.append("codex")
    return detected


def manual_install_hint():
    """Print manual install guidance when no known agent is detected."""
    print("No supported agents detected (Claude Code / Codex).")
    print("Manual install steps:")
    print(f"  1) Claude: copy {ROOT_SKILL_FILE} -> ~/.claude/skills/geosql/SKILL.md")
    print(f"     and {ROOT_REFERENCES_DIR} -> ~/.claude/skills/geosql/references/")
    print(f"  2) Codex:  copy {ROOT_SKILL_FILE} -> ~/.codex/skills/geosql/SKILL.md")
    print(f"     and {ROOT_REFERENCES_DIR} -> ~/.codex/skills/geosql/references/")
    return 1


def run_interactive_install():
    """Run interactive default installer flow for plain `geosql`."""
    print_banner()
    detected = detect_installed_agents()
    if not detected:
        return manual_install_hint()

    labels = []
    targets = []
    if "claude" in detected:
        labels.append("Install for Claude Code")
        targets.append("claude")
    if "codex" in detected:
        labels.append("Install for Codex")
        targets.append("codex")
    if len(detected) > 1:
        labels.append("Install for All detected")
        targets.append("all")

    if is_interactive_terminal():
        choice = select_menu_option("Confirm install target", labels, default_index=len(labels) - 1 if len(labels) > 1 else 0)
    else:
        choice = None

    if choice == "cancel":
        print("Install cancelled.")
        return 1

    if choice is None:
        print("Detected agents: " + ", ".join(detected))
        default_index = len(labels) - 1 if len(labels) > 1 else 0
        default_human = str(default_index + 1)
        for index, label in enumerate(labels, start=1):
            print(f"  {index}) {label}")
        raw = input(f"Select [1-{len(labels)}] (default: {default_human}): ").strip() if is_interactive_terminal() else ""
        if raw.isdigit() and 1 <= int(raw) <= len(labels):
            picked = int(raw) - 1
        else:
            picked = default_index
    else:
        picked = int(choice)

    selected_target = targets[picked]
    print(f"Installing target: {labels[picked]}")
    return handle_install_target(selected_target)


def handle_install_target(target):
    """Install for one target or all."""
    if target == "claude":
        return install_claude_skill()
    if target == "codex":
        return install_codex_skill()
    if target == "all":
        code = 0
        code = max(code, install_claude_skill())
        code = max(code, install_codex_skill())
        return code
    print(f"Unsupported install target: {target}", file=sys.stderr)
    return 2


def main():
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "install":
        raise SystemExit(handle_install_target(args.target))

    raise SystemExit(run_interactive_install())


if __name__ == "__main__":
    main()
