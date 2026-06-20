#!/usr/bin/env python3
"""Inject the paragraph-precise topical index into the EPUB's combined markdown,
BEFORE pandoc. Two edits:

  1. Stamp an invisible anchor `[]{#ix-<id>}` at the start of each located
     paragraph (matched by the entry's verbatim phrase, scoped to its section).
  2. Replace the Appendix Q body with the generated A-Z index whose entries link
     to those anchors (`[Chapter 15](#ix-...)`).

Pandoc's epub writer rewrites each internal `#ix-...` link to the correct split
file (verified), so the digital index is clickable to the exact paragraph -- no
page numbers needed. Usage: inject_epub_index.py <combined_md> <index_json>
No-op (exit 0) if the index data file is absent.
"""
import sys, os, re, json

_engine_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_engine_dir, 'indexing'))
sys.path.insert(0, _engine_dir)
import index_anchors

if len(sys.argv) < 3 or not os.path.exists(sys.argv[2]):
    sys.exit(0)

md_path, data_path = sys.argv[1], sys.argv[2]
entries = index_anchors.load_entries(data_path)
locations = index_anchors.assign_ids(entries)
text = open(md_path, encoding='utf-8').read()

# --- Split off the index/back-matter so we only stamp anchors in the body ---
# Body = everything before the Scripture Index (the first back-matter section).
# Anchors live in the chapters/appendices A-O, all before it. The back-matter headings
# are now plain ("# Scripture Index"), not "# Appendix P:"; match both forms.
mP = re.search(r'^#\s+(?:Scripture Index|Appendix\s+P:)', text, re.M)
body = text[:mP.start()] if mP else text
tail = text[mP.start():] if mP else ''

# --- Parse body into blocks (blank-line separated), tracking each block's section ---
def section_of(heading):
    m = re.match(r'#\s+Chapter\s+(\d+)\b', heading)
    if m:
        return f"Chapter {m.group(1)}"
    m = re.match(r'#\s+Appendix\s+([A-Z]\d*)\b', heading)
    if m:
        return f"Appendix {m.group(1)}"
    m = re.match(r'#\s+(Prologue|Preface|Epilogue|Afterword|How This Book Talks|Acknowledgments)\b', heading)
    if m:
        return m.group(1)
    return None

raw_blocks = re.split(r'(\n\s*\n)', body)   # keep separators to reassemble exactly
blocks = []   # (index_in_raw, text, section)
cur_section = None
for i, b in enumerate(raw_blocks):
    if i % 2 == 1:
        continue  # separator
    s = section_of(b.lstrip())
    if s:
        cur_section = s
    blocks.append((i, b, cur_section))

# precompute normalized block text + bucket by section
norm_blocks = [(i, b, sec, index_anchors._norm(b)) for (i, b, sec) in blocks]
buckets = {}
for nb in norm_blocks:
    buckets.setdefault(nb[2], []).append(nb)

stamped = set()
anchors_for_block = {}   # raw_index -> [ids]
for loc in locations:
    cands = index_anchors.phrase_candidates(loc['phrase'])
    if not cands:
        continue
    scope = buckets.get(loc.get('section'))
    hit = None
    for ph in cands:
        for (i, b, sec, nt) in (scope or []):
            if ph in nt:
                hit = i; break
        if hit is None:
            for (i, b, sec, nt) in norm_blocks:
                if ph in nt:
                    hit = i; break
        if hit is not None:
            break
    if hit is None:
        continue
    anchors_for_block.setdefault(hit, []).append(loc['id'])
    stamped.add(loc['id'])

# apply anchors: prepend the span(s) to each matched block
for i, ids in anchors_for_block.items():
    span = ''.join(f'[]{{#{aid}}}' for aid in ids)
    blk = raw_blocks[i]
    lead = len(blk) - len(blk.lstrip())
    # heading/list/table/quote/code blocks: put the anchors on their own line just
    # before; plain paragraphs: inline at the start.
    stripped = blk.lstrip()
    if stripped[:1] in ('#', '>', '-', '*', '|', '`', '+') or stripped[:2] == '  ':
        raw_blocks[i] = blk[:lead] + span + '\n\n' + stripped
    else:
        raw_blocks[i] = blk[:lead] + span + stripped
body = ''.join(raw_blocks)

# --- Replace the Appendix Q body with the generated, linked index ---
# keep the H1 + intro paragraph; swap everything until the next "# Appendix R".
for e in entries:
    e['locations'] = [l for l in e['locations'] if l['id'] in stamped]
index_md = index_anchors.render_index_markdown(entries, 'web')

qm = re.search(r'(^#\s+(?:Topical Index|Appendix\s+Q:)[^\n]*\n)(.*?)(?=^#\s+(?:Glossary of Terms|Glossary|Appendix\s+R)\b|\Z)',
               tail, re.M | re.S)
if qm:
    qbody = qm.group(2)
    # keep the first non-empty paragraph (intro) after the H1
    intro_m = re.match(r'\s*\n(.*?\n)\s*\n', qbody, re.S)
    intro = intro_m.group(1).strip() if intro_m else ''
    new_q = qm.group(1) + ('\n' + intro + '\n' if intro else '\n') + '\n' + index_md + '\n\n'
    tail = tail[:qm.start()] + new_q + tail[qm.end():]

open(md_path, 'w', encoding='utf-8').write(body + tail)
sys.stderr.write(f"[epub-index] stamped {len(stamped)}/{len(locations)} anchors; "
                 f"index entries: {len(entries)}\n")
