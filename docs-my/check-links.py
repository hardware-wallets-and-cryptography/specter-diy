#!/usr/bin/env python3
"""Check relative Markdown links under docs-my/.

Verifies two things for every relative link target:

1. the path resolves, and
2. a ``#Lnn`` / ``#Lnn-Lmm`` anchor falls inside the file.

It cannot detect content drift — a line number that still exists but now points
at unrelated code — so it is a floor, not a guarantee. See AD-01 in
``docs-my/audit/audit-comparison.md`` for the failure this guards against.

Needs the submodules checked out; embit, f469-disco, and bootloader paths are
cited heavily and read as missing otherwise.

Usage: python3 docs-my/check-links.py [root]   (default root: repo root)
Exit status 1 if anything is broken.
"""
import re
import sys
from pathlib import Path

LINK = re.compile(r"\]\(\s*(<[^>]*>|[^)\s]+)")
ANCHOR = re.compile(r"^L(\d+)(?:-L(\d+))?$")
CODE_SPAN = re.compile(r"`+[^`]*`+")
FENCE = re.compile(r"^\s{0,3}(```+|~~~+)")
SKIP_SCHEME = ("http://", "https://", "mailto:", "ftp://", "#")


def line_count(path: Path) -> int:
    with path.open("rb") as fh:
        return sum(1 for _ in fh)


def prose_lines(text: str):
    """Yield (lineno, line) outside fenced blocks, with code spans blanked.

    Both carry illustrative link syntax that is not meant to resolve.
    """
    fence = None
    for lineno, line in enumerate(text.split("\n"), 1):
        m = FENCE.match(line)
        if m:
            marker = m.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            continue
        if fence is not None:
            continue
        yield lineno, CODE_SPAN.sub("", line)


def check(root: Path) -> int:
    errors = []
    for md in sorted(root.glob("docs-my/**/*.md")):
        text = md.read_text(encoding="utf-8", errors="replace")
        for lineno, line in prose_lines(text):
            for raw in LINK.findall(line):
                target = raw[1:-1] if raw.startswith("<") else raw
                if target.startswith(SKIP_SCHEME):
                    continue
                path_part, _, frag = target.partition("#")
                if not path_part:
                    continue
                dest = (md.parent / path_part).resolve()
                where = f"{md.relative_to(root)}:{lineno}"
                if not dest.exists():
                    errors.append(f"{where}: missing path {target}")
                    continue
                m = ANCHOR.match(frag)
                if not m or not dest.is_file():
                    continue
                last = int(m.group(2) or m.group(1))
                total = line_count(dest)
                if last > total:
                    errors.append(
                        f"{where}: anchor #{frag} past end of {path_part} "
                        f"({total} lines)"
                    )
    for e in errors:
        print(f"BROKEN: {e}")
    print(f"{len(errors)} broken link(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    base = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    sys.exit(check(base.resolve()))
