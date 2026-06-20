#!/usr/bin/env python3
"""Make the WEB glossary's "See Chapter N / Appendix X" references precise, clickable
deep links (they ship as plain text today; only the topical index is clickable on web).

Mirrors inject_web_index.py. Two edits:
  1. Stamp an invisible <span id="glx-N"> at each glossary locator's discussion phrase
     in the chapter/appendix HTML file that owns its section (word-window retry for
     cross-block phrases).
  2. In appendix-r.html, wrap each entry's "Chapter N"/"Appendix X" mention in a link
     to "/mind/chapter/<slug>#glx-N" -- but only the chapters/appendices for which that
     headword actually has a stamped discussion anchor.

Anchors are stamped into RENDERED html only; the manuscript .md stays pristine.
Usage: inject_web_glossary.py <chapters_dir> <glossary_json>
No-op (exit 0) if the glossary data file is absent.
"""
import sys, os, re, json
from collections import defaultdict

_engine_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_engine_dir, 'indexing'))
sys.path.insert(0, _engine_dir)
import index_anchors

if len(sys.argv) < 3 or not os.path.exists(sys.argv[2]):
    sys.exit(0)

chapters_dir, data_path = sys.argv[1], sys.argv[2]
glossary = json.load(open(data_path, encoding='utf-8'))

_NAMED = {
    'Afterword': 'afterword', 'Epilogue': 'epilogue', 'Preface': 'preface',
    'Prologue': 'prologue', 'How This Book Talks': 'how-this-book-talks',
    'Acknowledgments': 'acknowledgments',
}


def section_to_slug(section):
    m = re.match(r'Chapter (\d+)$', section)
    if m:
        return m.group(1)
    m = re.match(r'Appendix ([A-Z]\d*)$', section)
    if m:
        return 'appendix-' + m.group(1).lower()
    return _NAMED.get(section)


def slug_to_file(slug):
    if slug.isdigit():
        return f'chapter-{int(slug):02d}.html'
    return f'{slug}.html'


def gloss_norm(s):
    return re.sub(r'\s+', ' ', s).strip().lower()


def windows(phrase):
    words = re.findall(r"\S+", phrase or "")
    for size in range(min(9, len(words)), 5, -1):
        if len(words) >= size:
            yield ' '.join(words[-size:])
            yield ' '.join(words[:size])


# --- 1. assign ids + stamp anchors into each section's file ----------------------
n = 0
by_section = defaultdict(list)   # section -> [(gid, phrase, term_norm)]
for e in glossary:
    tnorm = gloss_norm(e['term'])
    for loc in e.get('locations', []):
        ph, sec = loc.get('phrase'), loc.get('section', '')
        if not ph:
            continue
        n += 1
        by_section[sec].append((f'glx-{n}', ph, tnorm))

# (term_norm, section) -> (glx_id, slug)
anchor_for = {}
stamped = 0
for section, items in sorted(by_section.items()):
    slug = section_to_slug(section)
    if not slug:
        continue
    fpath = os.path.join(chapters_dir, slug_to_file(slug))
    if not os.path.exists(fpath):
        continue
    html = open(fpath, encoding='utf-8').read()
    for gid, ph, tnorm in items:
        # The file is exactly one section, so first-occurrence == in-section.
        new, res, _ = index_anchors.stamp_anchors(html, [{'id': gid, 'phrase': ph, 'section': section}])
        if not res:
            for w in windows(ph):
                new, res, _ = index_anchors.stamp_anchors(html, [{'id': gid, 'phrase': w, 'section': section}])
                if res:
                    break
        if res:
            html = new
            stamped += 1
            anchor_for.setdefault((tnorm, section), (gid, slug))
    open(fpath, 'w', encoding='utf-8').write(html)

# --- 2. wrap glossary "Chapter N / Appendix X" mentions in deep links -------------
rpath = os.path.join(chapters_dir, 'appendix-r.html')
linked = [0]
if os.path.exists(rpath) and anchor_for:
    rhtml = open(rpath, encoding='utf-8').read()

    _SEP = r'(?:\s*(?:,\s*and|and|,|[-–—])\s*)'

    def _entry(em):
        para = em.group(0)
        hm = re.search(r'<strong>(.+?)\.?</strong>', para)
        if not hm:
            return para
        tnorm = gloss_norm(hm.group(1))

        def _a(label, sec):
            a = anchor_for.get((tnorm, sec))
            if a:
                linked[0] += 1
                return f'<a href="/mind/chapter/{a[1]}#{a[0]}" class="xref">{label}</a>'
            return label

        # "Chapter 6" / "Chapters 8, 11, and 25" -- link each number to its anchor.
        def _chapters(m):
            return m.group(1) + re.sub(r'\d+', lambda nm: _a(nm.group(0), f'Chapter {int(nm.group(0))}'), m.group(2))
        para = re.sub(r'(?<![<="\w/])((?:Chapters|Chapter|Chs\.|Ch\.)\s+)(\d+(?:' + _SEP + r'\d+)*)', _chapters, para)

        # "Appendix A1" / "Appendices A1 and J"
        _APPTOK = r'A1[0-2]|A[1-9]|[B-S](?![a-z])'
        def _apps(m):
            return m.group(1) + re.sub(_APPTOK, lambda am: _a(am.group(0), f'Appendix {am.group(0).upper()}'), m.group(2))
        para = re.sub(r'(?<![<="\w/])((?:Appendices|Appendix|App\.)\s+)(' + _APPTOK + r'(?:' + _SEP + _APPTOK + r')*)', _apps, para)
        return para

    rhtml = re.sub(r'<p>.*?</p>', _entry, rhtml, flags=re.S)
    open(rpath, 'w', encoding='utf-8').write(rhtml)

print(f"  web glossary: stamped {stamped} discussion anchors; linked {linked[0]} refs",
      file=sys.stderr)
