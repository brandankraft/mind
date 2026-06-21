#!/usr/bin/env python3
"""stamp_version.py -- single-source version/printing line for the copyright page.

Reads `version` + `version_date` from editions/<edition>/config/edition.toml,
grabs the current git short-hash, and regenerates the printing line inside BOTH
copyright surfaces (the print/EPUB markdown AND the static web HTML) so they can
never drift apart again.

The line lives at the foot of the copyright (verso) page -- the traditional home
of the edition/printing notice. The git short-hash lets you match any physical
proof in hand to the exact source commit it was built from.

Usage:
    python3 engine/stamp_version.py [edition]      # default: 1st-edition

Idempotent: re-run any time. The block is delimited by sentinel comments, so
everything outside the markers is left untouched.

Versioning convention (major.minor.patch):
    major = new edition          minor = content change (pages may move)
    patch = corrections/cleanup with no pagination change
"""
import sys
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path

START = "VERSION-BLOCK:START"
END = "VERSION-BLOCK:END"

ROOT = Path(__file__).resolve().parent.parent


def git_short_hash() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip() or "unknown"
    except Exception:
        return "unknown"


def replace_block(text: str, start_marker: str, end_marker: str, body: str) -> str:
    """Replace content between <!-- START --> and <!-- END --> markers."""
    s = text.find(start_marker)
    e = text.find(end_marker)
    if s == -1 or e == -1 or e < s:
        raise SystemExit(
            f"ERROR: sentinel markers ({START} / {END}) not found or out of order.\n"
            "Add them around the printing line in the copyright file first."
        )
    # Keep both marker lines; swap everything between them. `body` ends with \n.
    s_line_end = text.find("\n", s)            # end of the START-marker line
    e_line_start = text.rfind("\n", 0, e) + 1  # start of the END-marker line
    return text[: s_line_end + 1] + body + text[e_line_start:]


def stamp(edition: str = "1st-edition") -> None:
    edir = ROOT / "editions" / edition
    cfg = tomllib.loads((edir / "config" / "edition.toml").read_text())
    version = cfg.get("version", "1.0")
    version_date = cfg.get("version_date", "")
    githash = git_short_hash()
    build_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Reader-facing printing line (two physical lines). Middot = not a dash.
    line1 = f"First Edition · Version {version}"
    line2 = f"Revised {version_date} · build {githash}"

    md_path = edir / "content" / "front-matter" / "03-copyright.md"
    html_path = edir / "static-chapters" / "copyright.html"

    # --- Markdown (print + EPUB): two-space line break, KJV-style hard wrap ---
    md_body = f"{line1}  \n{line2}\n"
    md = md_path.read_text()
    md = replace_block(md, START, END, md_body)
    md_path.write_text(md)

    # --- Static HTML (web) ---
    html_body = f"<p>{line1}<br>\n{line2}</p>\n"
    html = html_path.read_text()
    html = replace_block(html, START, END, html_body)
    html_path.write_text(html)

    # --- Machine-readable provenance record ---
    (edir / "VERSION.txt").write_text(
        f"version: {version}\n"
        f"version_date: {version_date}\n"
        f"git_hash: {githash}\n"
        f"build_timestamp: {build_ts}\n"
    )

    print(f"[stamp] {version}  ({version_date})  build {githash}")
    print(f"[stamp] line1: {line1}")
    print(f"[stamp] line2: {line2}")
    print(f"[stamp] updated: {md_path.relative_to(ROOT)}")
    print(f"[stamp] updated: {html_path.relative_to(ROOT)}")
    print(f"[stamp] wrote:   {(edir / 'VERSION.txt').relative_to(ROOT)}")


if __name__ == "__main__":
    stamp(sys.argv[1] if len(sys.argv) > 1 else "1st-edition")
