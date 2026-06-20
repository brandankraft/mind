#!/usr/bin/env python3
"""Retarget the EPUB glossary's "See Chapter N / Appendix X" links from the chapter
HEADING to the exact DISCUSSION paragraph, mirroring what the PDF build does.

Runs on the combined markdown AFTER the cross-reference linkifier (so the glossary's
chapter refs are already `[Chapter 8](#chapter-8-slug)`) and AFTER inject_epub_index
(so its ix-anchors are already placed). Two edits:

  1. Stamp an invisible `[]{#glx-N}` anchor at each glossary locator's discussion
     phrase in the body (scoped to its section; word-window retry for cross-block
     phrases), building a (term_norm, section) -> glx-N map.
  2. In the glossary div, retarget each entry's chapter/appendix link to that entry's
     own discussion anchor.

Pandoc rewrites each `#glx-N` to the correct split file, so the EPUB glossary link
lands on the exact paragraph. Usage: inject_epub_glossary.py <combined_md> <glossary_json>
No-op (exit 0) if the glossary data file is absent.
"""
import sys, os, re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_anchors

if len(sys.argv) < 3 or not os.path.exists(sys.argv[2]):
    sys.exit(0)

md_path, data_path = sys.argv[1], sys.argv[2]
import json
glossary = json.load(open(data_path, encoding='utf-8'))
text = open(md_path, encoding='utf-8').read()


def _gloss_norm(s):
    return re.sub(r'\s+', ' ', s).strip().lower()


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


def _windows(phrase):
    words = re.findall(r"\S+", phrase or "")
    for size in range(min(9, len(words)), 5, -1):
        if len(words) >= size:
            yield ' '.join(words[-size:])
            yield ' '.join(words[:size])


# --- body = everything before the Scripture Index (first back-matter section);
# only stamp anchors there. The glossary div lives in the tail. Match plain headings
# ("# Scripture Index") and the legacy "# Appendix P:" form. ---
mP = re.search(r'^#\s+(?:Scripture Index|Appendix\s+P:)', text, re.M)
body = text[:mP.start()] if mP else text
tail = text[mP.start():] if mP else ''

raw_blocks = re.split(r'(\n\s*\n)', body)
blocks, cur = [], None
for i, b in enumerate(raw_blocks):
    if i % 2 == 1:
        continue
    s = section_of(b.lstrip())
    if s:
        cur = s
    blocks.append((i, b, cur))
norm_blocks = [(i, b, sec, index_anchors._norm(b)) for (i, b, sec) in blocks]
buckets = {}
for nb in norm_blocks:
    buckets.setdefault(nb[2], []).append(nb)


def find_block(phrase, section):
    """raw_blocks index of the in-section block holding the phrase (full phrase, then
    word-windows), or None."""
    for cand in [phrase] + list(_windows(phrase)):
        cands = index_anchors.phrase_candidates(cand)
        for ph in cands:
            for (i, b, sec, nt) in buckets.get(section, []):
                if ph in nt:
                    return i
    return None


anchors_for_block = {}
anchor_id = {}     # (term_norm, section) -> glx-N
n = 0
for e in glossary:
    tnorm = _gloss_norm(e['term'])
    for loc in e.get('locations', []):
        ph, sec = loc.get('phrase'), loc.get('section', '')
        if not ph:
            continue
        i = find_block(ph, sec)
        if i is None:
            continue
        n += 1
        gid = f'glx-{n}'
        anchors_for_block.setdefault(i, []).append(gid)
        anchor_id.setdefault((tnorm, sec), gid)

for i, ids in anchors_for_block.items():
    span = ''.join(f'[]{{#{aid}}}' for aid in ids)
    blk = raw_blocks[i]
    lead = len(blk) - len(blk.lstrip())
    stripped = blk.lstrip()
    if stripped[:1] in ('#', '>', '-', '*', '|', '`', '+') or stripped[:2] == '  ':
        raw_blocks[i] = blk[:lead] + span + '\n\n' + stripped
    else:
        raw_blocks[i] = blk[:lead] + span + stripped
body = ''.join(raw_blocks)


# --- retarget glossary entry links to discussion anchors ---
def section_from_slug(slug):
    m = re.match(r'chapter-(\d+)-', slug)
    if m:
        return f'Chapter {int(m.group(1))}'
    m = re.match(r'appendix-([a-z]\d*)-', slug)
    if m:
        return f'Appendix {m.group(1).upper()}'
    return None


retargeted = [0]
_SEP = r'(?:\s*(?:,\s*and|and|,|[-–—])\s*)'
_APPTOK = r'A1[0-2]|A[1-9]|[B-S](?![a-z])'


def _retarget_entry(em):
    """Per glossary entry: revert the cross-ref linkifier's chapter/appendix links to
    plain text, then re-link each chapter/appendix number (singular AND plural runs)
    to THIS headword's discussion anchor. Mirrors the web injector."""
    para = em.group(0)
    hm = re.search(r'\*\*(.+?)\.?\*\*', para)
    if not hm:
        return para
    tnorm = _gloss_norm(hm.group(1))
    # 1. revert build-book's chapter/appendix markdown links to plain text
    para = re.sub(r'\[([^\]]*)\]\(#(?:chapter-\d+|appendix-[a-z]\d*)-[^)]+\)', r'\1', para)

    def _a(label, sec):
        gid = anchor_id.get((tnorm, sec))
        if gid:
            retargeted[0] += 1
            return f'[{label}](#{gid})'
        return label

    def _ch(m):
        return m.group(1) + re.sub(r'\d+', lambda nm: _a(nm.group(0), f'Chapter {int(nm.group(0))}'), m.group(2))
    para = re.sub(r'(?<!\[)((?:Chapters|Chapter|Chs\.|Ch\.)\s+)(\d+(?:' + _SEP + r'\d+)*)', _ch, para)

    def _ap(m):
        return m.group(1) + re.sub(_APPTOK, lambda am: _a(am.group(0), f'Appendix {am.group(0).upper()}'), m.group(2))
    para = re.sub(r'(?<!\[)((?:Appendices|Appendix|App\.)\s+)(' + _APPTOK + r'(?:' + _SEP + _APPTOK + r')*)', _ap, para)
    return para


# The glossary (Appendix R) lives in the TAIL (after Appendix P); retarget it there.
gm = re.search(r'(<div class="glossary">)(.*?)(</div>)', tail, re.S)
if gm:
    glossary_body = re.sub(r'\*\*[^\n]+?\*\*[^\n]*(?:\n(?!\n)[^\n]*)*', _retarget_entry, gm.group(2))
    tail = tail[:gm.start(2)] + glossary_body + tail[gm.end(2):]

open(md_path, 'w', encoding='utf-8').write(body + tail)
sys.stderr.write(f"[epub-glossary] stamped {n} discussion anchors; "
                 f"retargeted {retargeted[0]} glossary links\n")
