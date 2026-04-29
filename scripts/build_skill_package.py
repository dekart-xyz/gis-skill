#!/usr/bin/env python3
"""Build geosql.skill package from canonical sources under geosql/."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "geosql"
SKILL = PKG_DIR / "SKILL.md"
REFS_DIR = PKG_DIR / "references"
OUT = ROOT / "geosql.skill"

if not SKILL.exists():
    raise SystemExit(f"Missing skill file: {SKILL}")

with ZipFile(OUT, "w", compression=ZIP_DEFLATED) as zf:
    zf.write(SKILL, arcname="geosql/SKILL.md")
    if REFS_DIR.exists() and REFS_DIR.is_dir():
        for path in sorted(REFS_DIR.rglob("*")):
            if path.is_file():
                zf.write(path, arcname=f"geosql/references/{path.relative_to(REFS_DIR)}")

print(f"Built {OUT}")
