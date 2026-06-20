#!/usr/bin/env python3
"""Inject the paragraph-precise topical index (Appendix Q) into the WEB build.

The web book is one HTML file per section (public_html/book-content/chapters/),
served at /mind/chapter/<slug>. So unlike the EPUB/PDF (single combined doc), the
index lives on its OWN page and must deep-link ACROSS pages. Two edits:

  1. Stamp an invisible <span id="ix-..."> at the start of each located paragraph,
     in the chapter/appendix HTML file that owns that section.
  2. Rebuild appendix-q.html's body as the generated A-Z index, each location a
     clickable link to "/mind/chapter/<target-slug>#ix-..." labeled by section.

Anchors are stamped into the RENDERED html only; the manuscript .md stays pristine.
Shares all matching/rendering logic with index_anchors.py (same as PDF + EPUB).

Usage: inject_web_index.py <chapters_dir> <index_json>
No-op (exit 0) if the index data file is absent.
"""
import sys, os, re, subprocess
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_anchors

if len(sys.argv) < 3 or not os.path.exists(sys.argv[2]):
    sys.exit(0)

chapters_dir, data_path = sys.argv[1], sys.argv[2]

# --- section label (as it appears in the index data) -> web url slug -------------
_NAMED = {
    'Afterword': 'afterword', 'Epilogue': 'epilogue', 'Preface': 'preface',
    'Prologue': 'prologue', 'How This Book Talks': 'how-this-book-talks',
    'Acknowledgments': 'acknowledgments',
}


def section_to_slug(section):
    m = re.match(r'Chapter (\d+)$', section)
    if m:
        return m.group(1)                       # /mind/chapter/13
    m = re.match(r'Appendix ([A-Z]\d*)$', section)
    if m:
        return 'appendix-' + m.group(1).lower()  # /mind/chapter/appendix-a1
    return _NAMED.get(section)


def slug_to_file(slug):
    # Chapter pages are zero-padded on disk (chapter-01.html); everything else is
    # its slug verbatim (appendix-a1.html, prologue.html, ...).
    if slug.isdigit():
        return f'chapter-{int(slug):02d}.html'
    return f'{slug}.html'


# --- 1. assign ids + stamp anchors into each section's file ----------------------
entries = index_anchors.load_entries(data_path)
locations = index_anchors.assign_ids(entries)

by_section = defaultdict(list)
for loc in locations:
    by_section[loc['section']].append(loc)

resolved = set()
id_to_slug = {}
missing_files, unknown_sections = [], []

for section, locs in sorted(by_section.items()):
    slug = section_to_slug(section)
    if not slug:
        unknown_sections.append(section)
        continue
    fpath = os.path.join(chapters_dir, slug_to_file(slug))
    if not os.path.exists(fpath):
        missing_files.append(fpath)
        continue
    html = open(fpath, encoding='utf-8').read()
    html, res, _unres = index_anchors.stamp_anchors(html, locs)
    open(fpath, 'w', encoding='utf-8').write(html)
    for rid in res:
        resolved.add(rid)
    for loc in locs:
        id_to_slug[loc['id']] = slug

# --- 2. prune to resolved locations + render the A-Z index -----------------------
for e in entries:
    e['locations'] = [l for l in e['locations'] if l['id'] in resolved]

index_md = index_anchors.render_index_markdown(entries, 'web')
index_html = subprocess.run(
    ['pandoc', '--from', 'markdown+smart', '--to', 'html5'],
    input=index_md, capture_output=True, text=True).stdout
index_html = index_html.replace('–', '—')

# Rewrite intra-doc "#ix-..." links to the target page they live on.
def _retarget(m):
    iid = m.group(1)
    slug = id_to_slug.get(iid)
    return f'href="/mind/chapter/{slug}#{iid}"' if slug else m.group(0)

index_html = re.sub(r'href="#(ix-[^"]+)"', _retarget, index_html)

# --- 3. splice into appendix-q.html: keep its <h1> + intro <p>, swap the body ----
qpath = os.path.join(chapters_dir, 'appendix-q.html')
q = open(qpath, encoding='utf-8').read()
m = re.search(r'<h1\b.*?</h1>\s*(?:<p\b.*?</p>\s*)?', q, re.S)
head = m.group(0) if m else '<h1>Topical Index</h1>\n'
open(qpath, 'w', encoding='utf-8').write(
    head + '\n<div class="topical-index">\n' + index_html + '\n</div>\n')

print(f"  web topical index: stamped {len(resolved)}/{len(locations)} anchors "
      f"across {len({s for s in id_to_slug.values()})} pages", file=sys.stderr)
if unknown_sections:
    print(f"  !! unknown index sections (skipped): {sorted(set(unknown_sections))}", file=sys.stderr)
if missing_files:
    print(f"  !! missing chapter files (skipped): {missing_files}", file=sys.stderr)
