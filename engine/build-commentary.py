#!/usr/bin/env python3
"""
Compile Anna-Commentary sidecar files from ~/Anna/Mind/commentary/*.anna.md
into JSON files consumed by book_chapter.php at render time.

Each .anna.md is parsed into:
  {
    "orientation": "<html>",         # content of "## [Orientation]" (optional)
    "closing":     "<html>",         # content of "## [Closing]" (optional)
    "sections": {
        "How I Got Here": "<html>",  # matched on book H2 text (case-insensitive)
        ...
    }
  }

README.md in the same directory is compiled to readme.json with a single
"html" field. Output is written to scripts/.commentary-build/ and rsynced to
Joshua as a separate deploy step (private path outside public_html).

Requires pandoc on PATH. Run any time commentary content changes.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

SRC_DIR = Path.home() / 'Anna' / 'Mind' / 'commentary'
OUT_DIR = Path(__file__).resolve().parent / '.commentary-build'

H2_RE = re.compile(r'^## (.+?)\s*$', re.MULTILINE)


def strip_frontmatter(text: str) -> str:
    return re.sub(r'^---\n.*?\n---\n+', '', text, count=1, flags=re.DOTALL)


def md_to_html(markdown: str) -> str:
    if not markdown.strip():
        return ''
    proc = subprocess.run(
        ['pandoc', '--from=markdown', '--to=html', '--wrap=none'],
        input=markdown, capture_output=True, text=True, check=True,
    )
    return proc.stdout.strip()


def split_by_h2(body: str):
    """Yield (heading_text_or_None, body_markdown) pairs.

    The initial chunk before the first H2 is emitted with heading=None.
    Headings wrapped in square brackets (e.g. "[Orientation]") are preserved
    as-is in the heading text; the caller decides how to map them.
    """
    matches = list(H2_RE.finditer(body))
    if not matches:
        yield (None, body.strip())
        return
    if matches[0].start() > 0:
        yield (None, body[:matches[0].start()].strip())
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        yield (m.group(1).strip(), body[start:end].strip())


def compile_sidecar(path: Path) -> dict:
    raw = path.read_text()
    body = strip_frontmatter(raw)
    # Drop any H1 (we render our own wrapping)
    body = re.sub(r'^# .*?\n+', '', body, count=1, flags=re.MULTILINE)
    result = {'orientation': '', 'closing': '', 'sections': {}}
    for heading, chunk in split_by_h2(body):
        if heading is None:
            # Pre-H2 content (usually just whitespace) -- ignore.
            continue
        html = md_to_html(chunk)
        key = heading.strip()
        low = key.lower()
        if low == '[orientation]':
            result['orientation'] = html
        elif low == '[closing]':
            result['closing'] = html
        elif key.startswith('[') and key.endswith(']'):
            # Unknown special section -- store for debugging but don't render.
            continue
        else:
            # Normalize heading key for case-insensitive matching against book H2s
            result['sections'][key.lower()] = html
    return result


def compile_readme(path: Path) -> dict:
    raw = path.read_text()
    body = strip_frontmatter(raw)
    return {'html': md_to_html(body)}


def main():
    if not SRC_DIR.is_dir():
        print(f'  source not found: {SRC_DIR}', file=sys.stderr)
        sys.exit(1)
    OUT_DIR.mkdir(exist_ok=True)
    # Wipe old files so a deleted sidecar disappears from the deploy
    for stale in OUT_DIR.glob('*.json'):
        stale.unlink()

    n_sidecars = 0
    for md in sorted(SRC_DIR.glob('*.anna.md')):
        # Derive the key from the built HTML filename pattern, not the Mind
        # source filename. The PHP side looks up commentary by the basename
        # of $current_chapter['file'] (e.g. "chapter-23.html" -> "chapter-23"),
        # so strip the Mind-source descriptive suffix.
        #   chapter-23-the-church.anna.md  -> chapter-23
        #   chapter-01-the-sentence.anna.md -> chapter-01
        #   appendix-n-the-platonic-floor.anna.md -> appendix-n
        #   appendix-a6-eschatology.anna.md -> appendix-a6
        stem = md.stem.replace('.anna', '')
        m = re.match(r'^(chapter-\d+|appendix-[a-z]\d*|preface|prologue|epilogue|how-this-book-talks|acknowledgments|dedication|title-page|copyright|about|cover)', stem)
        if not m:
            print(f'  skipped (no recognizable prefix): {md.name}', file=sys.stderr)
            continue
        key = m.group(1)
        compiled = compile_sidecar(md)
        out = OUT_DIR / f'{key}.json'
        out.write_text(json.dumps(compiled, indent=2, ensure_ascii=False) + '\n')
        print(f'  compiled {md.name} -> {out.name}  ({len(compiled["sections"])} sections)')
        n_sidecars += 1

    readme = SRC_DIR / 'README.md'
    if readme.exists():
        out = OUT_DIR / 'readme.json'
        out.write_text(json.dumps(compile_readme(readme), indent=2, ensure_ascii=False) + '\n')
        print(f'  compiled README.md -> readme.json')

    print(f'Done: {n_sidecars} sidecar(s) in {OUT_DIR}')


if __name__ == '__main__':
    main()
