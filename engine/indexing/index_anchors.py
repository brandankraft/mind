"""Shared topical-index anchor machinery for ALL three book pipelines
(PDF via build-book-pdf.py, web via build-book.sh's transform chain, EPUB via
epub_enhance.py).

The topical index (Appendix Q) is paragraph-precise in every format. The single
source of truth is an index-data file: per headword, a list of LOCATIONS, each a
verbatim PHRASE copied from the manuscript plus the SECTION it lives in. At build
time we:

  1. stamp an invisible anchor id onto the block element (paragraph/li/blockquote/
     heading) whose text contains that phrase  -> stamp_anchors()
  2. render the A-Z index entries that link to those ids                -> render_index_html()

PDF resolves each link to a PAGE number via CSS target-counter (the same
mechanism the TOC uses). EPUB/web make each link clickable to the exact paragraph,
labeled by section name. One metadata source, both payoffs. The manuscript source
files stay pristine -- anchors are injected into the RENDERED html, never the .md.

Phrase matching is tolerant: tags stripped, whitespace collapsed, and smart
punctuation (curly quotes, em/en dashes) normalized on BOTH sides, so a phrase
copied from markdown still matches pandoc's typographically-cooked HTML.
"""

import re
import json
import unicodedata

_BLOCK_RE = re.compile(r'<(p|li|blockquote|h[1-6]|figcaption|td)\b([^>]*)>(.*?)</\1>',
                       re.DOTALL | re.IGNORECASE)
_TAG_RE = re.compile(r'<[^>]+>')
_WS_RE = re.compile(r'\s+')


def _norm(s):
    """Normalize for tolerant matching against pandoc's typographically-cooked HTML.
    The locator phrases are copied from the MARKDOWN source, so we must neutralize
    everything pandoc transforms: strip tags + markdown emphasis markers (* _),
    unify smart quotes, decode entities, and collapse every dash run (-- / en / em)
    AND surrounding space to a single space, then lowercase + collapse whitespace."""
    s = _TAG_RE.sub('', s)
    s = (s.replace('‘', "'").replace('’', "'")
           .replace('“', '"').replace('”', '"')
           .replace('…', '...').replace('\xa0', ' '))
    s = (s.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
           .replace('&quot;', '"').replace('&#39;', "'").replace('&rsquo;', "'")
           .replace('&lsquo;', "'").replace('&ldquo;', '"').replace('&rdquo;', '"')
           .replace('&mdash;', ' ').replace('&ndash;', ' ').replace('&hellip;', '...')
           .replace('&nbsp;', ' '))
    s = s.replace('*', '').replace('_', '')          # markdown emphasis markers
    s = re.sub(r'[‐-―\-]+', ' ', s)         # any hyphen/dash run -> space
    return _WS_RE.sub(' ', s).strip().lower()


def slugify(term):
    s = unicodedata.normalize('NFKD', term).encode('ascii', 'ignore').decode()
    s = re.sub(r'[^a-zA-Z0-9]+', '-', s).strip('-').lower()
    return s or 'x'


def assign_ids(entries):
    """Give every location a stable id ix-<term-slug>-<n>. Two locations that point
    at the SAME spot (identical phrase + section) SHARE one anchor id -- so two
    headwords describing the same paragraph (e.g. Aseity / Self-existence) both link
    to it. Mutates entries in place; returns the de-duplicated list of unique
    {id, phrase, section, term} anchor records to stamp."""
    registry = {}   # (norm_phrase, section) -> id
    locs = []
    for e in entries:
        base = slugify(e['term'] + ('-' + e['sub'] if e.get('sub') else ''))
        for i, loc in enumerate(e.get('locations', []), 1):
            key = (_norm(loc.get('phrase', '')), loc.get('section', ''))
            if key in registry:
                loc['id'] = registry[key]
                continue
            lid = f"ix-{base}-{i}"
            registry[key] = lid
            loc['id'] = lid
            locs.append({'id': lid, 'phrase': loc.get('phrase', ''),
                         'section': loc.get('section', ''), 'term': e['term']})
    return locs


def phrase_candidates(phrase):
    """Normalized full phrase first, then distinctive sub-segments (split on table
    pipes, newlines, arrows, '//') -- so a locator lifted from a table row, a
    multi-paragraph span, or an ASCII diagram still matches the rendered text."""
    cands = []
    full = _norm(phrase)
    if len(full) >= 8:
        cands.append(full)
    for s in sorted((_norm(x) for x in re.split(r'\||\n|->|=>|//|::|→', phrase)), key=len, reverse=True):
        if len(s) >= 12 and s != full and s not in cands:
            cands.append(s)
    return cands


def stamp_anchors(html, locations, section_spans=None):
    """Insert an invisible <span id=...> at the start of the block (paragraph/li/
    heading/blockquote) whose text contains each location's phrase.

    A span (not an id on the block tag) means one paragraph can host MANY anchors
    without clashing, and target-counter to the span gives the block's page.

    locations: list of {id, phrase, section}. section_spans (optional):
    section_label -> (start_char, end_char), limiting where a phrase may match to
    disambiguate phrases that recur across the book. Returns (html, resolved_ids,
    unresolved); unresolved = locations whose phrase wasn't found (a bad locator --
    callers should log them so the generating pass can repair)."""
    # Index every block once: insertion point is just past its opening tag.
    blocks = []
    for m in _BLOCK_RE.finditer(html):
        open_tag = f"<{m.group(1)}{m.group(2)}>"
        blocks.append((m.start(), m.start() + len(open_tag), _norm(m.group(3))))

    # Bucket blocks by section span so a scoped locator scans only its chapter's
    # ~100 blocks instead of all ~6000 (O(N*M) -> ~60x faster at book scale).
    buckets = {}
    if section_spans:
        span_items = sorted(section_spans.items(), key=lambda kv: kv[1][0])
        starts = [v[0] for _, v in span_items]
        import bisect
        for b in blocks:
            j = bisect.bisect_right(starts, b[0]) - 1
            if 0 <= j < len(span_items):
                lbl, (s0, s1) = span_items[j]
                if s0 <= b[0] <= s1:
                    buckets.setdefault(lbl, []).append(b)

    def candidates(phrase):
        """Full normalized phrase first, then distinctive sub-segments -- so a
        locator the agent lifted from a TABLE ROW ('Christology | Who is Christ?'),
        a MULTI-PARAGRAPH span ('...Mary.\\n\\nIncorrect...'), or an ASCII DIAGRAM
        ('God thinks -> information') still anchors to the cell/line it came from."""
        cands = []
        full = _norm(phrase)
        if len(full) >= 8:
            cands.append(full)
        segs = re.split(r'\||\n|->|=>|//|::|→', phrase)
        for s in sorted((_norm(x) for x in segs), key=len, reverse=True):
            if len(s) >= 12 and s != full and s not in cands:
                cands.append(s)
        return cands

    resolved, unresolved, edits = [], [], []
    for loc in locations:
        if not _norm(loc.get('phrase', '')):
            unresolved.append(loc); continue
        scoped = buckets.get(loc.get('section')) if buckets else None
        ins = None
        for ph in candidates(loc['phrase']):
            if scoped:                                  # fast: only this section's blocks
                for bstart, bins, btext in scoped:
                    if ph in btext:
                        ins = bins; break
            if ins is None:                             # fallback: scan all blocks
                for bstart, bins, btext in blocks:
                    if ph in btext:
                        ins = bins; break
            if ins is not None:
                break
        if ins is None:
            unresolved.append(loc); continue
        edits.append((ins, loc['id']))
        resolved.append(loc['id'])
    # apply right-to-left so offsets stay valid
    for ins, anchor_id in sorted(edits, key=lambda e: -e[0]):
        html = html[:ins] + f'<span id="{anchor_id}" class="ix-anchor"></span>' + html[ins:]
    return html, resolved, unresolved


def load_entries(path):
    """Load merged index entries from a JSON file: [{term, sub?, see_also?,
    locations:[{phrase, section}]}...]. Sorted A-Z by sort key."""
    with open(path, encoding='utf-8') as fh:
        entries = json.load(fh)
    return entries


def sort_key(term):
    """Index sort: case-insensitive, ignore leading articles/quotes/punct."""
    t = re.sub(r'^[\"\'“‘(]+', '', term.strip())
    t = re.sub(r'^(the|a|an)\s+', '', t, flags=re.IGNORECASE)
    return re.sub(r'[^a-z0-9 ]', '', t.lower())


def _esc(s):
    return (s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


_BIBLE_BOOKS = (
    "Genesis Exodus Leviticus Numbers Deuteronomy Joshua Judges Ruth Samuel Kings "
    "Chronicles Ezra Nehemiah Esther Job Psalm Psalms Proverbs Ecclesiastes Song "
    "Isaiah Jeremiah Lamentations Ezekiel Daniel Hosea Joel Amos Obadiah Jonah Micah "
    "Nahum Habakkuk Zephaniah Haggai Zechariah Malachi Matthew Mark Luke John Acts "
    "Romans Corinthians Galatians Ephesians Philippians Colossians Thessalonians "
    "Timothy Titus Philemon Hebrews James Peter Jude Revelation"
).split()
_BOOK_SET = set(_BIBLE_BOOKS)
_SCRIPTURE_RE = re.compile(r'^\d?\s*([A-Z][a-z]+)\b.*\b\d+(:\d+)?')


def is_scripture_ref(term):
    """True for canonical Scripture references (book + chapter[:verse]) -- those
    belong in Appendix P, not the topical index. Keeps extra-biblical works
    (1 Enoch, 1QHodayot, Community Rule) and concept headwords that merely cite a
    verse in parentheses."""
    t = term.strip().strip('"“”')
    m = _SCRIPTURE_RE.match(t)
    if not m or m.group(1) not in _BOOK_SET:
        return False
    # keep if there's substantial prose beyond the citation (a concept headword)
    return len(re.sub(r'[\d:\-–—,.\s]', '', t)) <= len(m.group(1)) + 6


def _refs_html(entry, fmt):
    """PDF: plain, deduped, sorted page numbers (precomputed in entry['_pages']).
    Web: clickable links to each location's anchor, labeled by section."""
    if fmt == 'pdf':
        return ', '.join(str(p) for p in entry.get('_pages', []))
    return ', '.join(
        f'<a class="ixref" href="#{l["id"]}">{_esc(l.get("section", ""))}</a>'
        for l in entry.get('locations', []))


def render_index_markdown(entries, fmt):
    """Generate the A-Z topical-index body as markdown (raw-HTML entries pandoc
    passes through). Proper index form: ONE alphabetical list with letter-group
    headers; subentries NEST under their main headword; see-also cross-refs are
    pruned to headwords that actually exist in the index.

    fmt == 'pdf' -> empty <a class="ixref"> whose CSS ::after prints the page via
    target-counter. fmt == 'web' -> clickable <a> labeled by its section."""
    entries = [e for e in entries if not is_scripture_ref(e['term'])]

    groups = {}   # term -> {main, subs, see}
    for e in entries:
        g = groups.setdefault(e['term'], {'main': None, 'subs': [], 'see': set()})
        for s in (e.get('see_also') or []):
            g['see'].add(s)
        if e.get('sub'):
            g['subs'].append(e)
        elif g['main'] is None:
            g['main'] = dict(e)
        else:
            g['main']['locations'] = g['main'].get('locations', []) + e.get('locations', [])
            g['main']['_pages'] = sorted(set(g['main'].get('_pages', []) + e.get('_pages', [])))

    valid = {sort_key(t) for t in groups}

    def see_html(see_set, self_term):
        refs = [_esc(s) for s in sorted(see_set)
                if sort_key(s) != sort_key(self_term) and sort_key(s) in valid]
        return (' <span class="ix-see"><em>see also</em> ' + ', '.join(refs) + '</span>') if refs else ''

    out, cur = [], None
    for term in sorted(groups, key=lambda t: (sort_key(t), t)):
        g = groups[term]
        sk = sort_key(term)
        letter = sk[0].upper() if sk and sk[0].isalpha() else '#'
        if letter != cur:
            cur = letter
            # Emit the letter-group header as explicit HTML (not "## {letter}"):
            # a bare "## #" for the numerals group is mangled by pandoc's ATX
            # trailing-hash rule into an empty <h2 id="section">. Raw HTML with a
            # stable id sidesteps that and is styled identically (.index-columns h2
            # / .ix-group). The blank lines keep it a block in pandoc markdown.
            gid = 'num' if letter == '#' else letter.lower()
            out.append(f'\n<h2 class="ix-group" id="ix-group-{gid}">{letter}</h2>\n')
        main = g['main']
        main_refs = _refs_html(main, fmt) if main else ''
        out.append(f"- <strong>{_esc(term)}</strong>"
                   + ((' ' + main_refs) if main_refs else '')
                   + see_html(g['see'], term))
        for s in sorted(g['subs'], key=lambda x: sort_key(x.get('sub', ''))):
            srefs = _refs_html(s, fmt)
            out.append(f"    - {_esc(s['sub'])}" + ((' ' + srefs) if srefs else ''))
    return '\n'.join(out)
