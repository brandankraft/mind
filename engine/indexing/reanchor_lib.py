#!/usr/bin/env python3
"""Re-anchoring engine for the index-precision project.

Loads the rendered book PDF once (page cache + section ranges, via
classify_index_anchors) and exposes:

  - load_pdf(pdf)                     -> (norm_pages, ranges)
  - resolves_in_section(cand, section, norm_pages, ranges) -> bool
  - section_source(section)           -> plain-prose text of the section's source .md
  - free_anchor(term, section, old_phrase, ...) -> new in-section phrase or None

Strategy for free_anchor (first candidate that resolves IN-SECTION wins):
  1. longest contiguous word-window (>=MIN_WORDS) of the OLD phrase -- preserves the
     author's curated discussion spot; recovers page-break / partial-render misses.
  2. clean prose windows from the section SOURCE around occurrences of the headword
     (and its surname / comma-flipped variants) -- a genuine discussion phrase, free.

Everything it returns is validated against the rendered PDF, so a returned phrase is
guaranteed to resolve in-section in that edition. Source prose is edition-independent,
so it should hold across trims (caller can spot-check the narrowest, 6x9).
"""
import os
import re
import sys
import glob

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_anchors
import classify_index_anchors as C

HOME = os.path.expanduser('~')
BOOK_DIR = os.path.join(HOME, 'Anna', 'Mind')

MIN_WORDS = 5          # shortest acceptable anchor phrase (words)
MAX_WORDS = 9          # target upper bound -- short phrases resolve more reliably

# ---------------------------------------------------------------- PDF loading
def load_pdf(pdf=C.DEFAULT_PDF):
    pages = C.build_page_cache(pdf)
    bm = C.find_backmatter_start(pages)
    starts, ranges, idx_cap = C.build_section_ranges(pages, bm)
    norm_pages = [(p, index_anchors._norm(t)) for p, t in pages]
    return norm_pages, ranges


def in_section_page(cand, section, norm_pages, ranges):
    """Page where `cand` (a normalized phrase) first appears inside `section`'s
    range, or None. `cand` must already be normalized via index_anchors._norm."""
    rng = ranges.get(C.seckey(section))
    if not rng or not cand:
        return None
    for p, t in norm_pages:
        if rng[0] <= p < rng[1] and cand in t:
            return p
    return None


def phrase_resolves(phrase, section, norm_pages, ranges):
    """True if any phrase_candidate of `phrase` appears in `section`'s page range."""
    for ph in index_anchors.phrase_candidates(phrase):
        if in_section_page(ph, section, norm_pages, ranges):
            return True
    return False


# ------------------------------------------------------- section source prose
_SECTION_FILE_CACHE = {}
_SECTION_PROSE_CACHE = {}


def _section_file(section):
    files = glob.glob(os.path.join(BOOK_DIR, '*.md'))
    base = {os.path.basename(f): f for f in files}
    m = re.match(r'Chapter (\d+)$', section or '')
    if m:
        pat = 'chapter-%02d-' % int(m.group(1))
        return next((f for n, f in base.items() if n.startswith(pat)), None)
    m = re.match(r'Appendix (A\d+)$', section or '')
    if m:
        pat = 'appendix-%s-' % m.group(1).lower()
        return next((f for n, f in base.items() if n.startswith(pat)), None)
    m = re.match(r'Appendix ([B-S])$', section or '')
    if m:
        pat = 'appendix-%s-' % m.group(1).lower()
        return next((f for n, f in base.items() if n.startswith(pat)), None)
    fm = {'Prologue': 'prologue.md', 'Preface': 'preface.md', 'Epilogue': 'epilogue.md',
          'Afterword': 'afterword.md', 'How This Book Talks': 'how-this-book-talks.md'}
    return base.get(fm.get(section, ''))


def _strip_to_prose(md):
    """Drop everything that renders unreliably (tables, code/diagram fences, headings,
    HTML, figure includes, image lines) and return the remaining prose as a list of
    paragraph strings. Blockquotes and list items are kept (they render as prose)."""
    out = []
    in_fence = False
    buf = []
    for line in md.splitlines():
        s = line.rstrip()
        if s.strip().startswith('```') or s.strip().startswith('~~~'):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        st = s.strip()
        if not st:
            if buf:
                out.append(' '.join(buf)); buf = []
            continue
        if st.startswith('#'):                      # heading
            if buf: out.append(' '.join(buf)); buf = []
            continue
        if st.startswith('|') or re.match(r'^[-:\s|]+$', st):   # table row / rule
            continue
        if st.startswith('<') or st.startswith('!['):           # html / image
            continue
        if st.startswith(':::'):                                # pandoc fenced div
            continue
        # strip leading markdown markers (>, -, *, digits.) and inline emphasis
        st = re.sub(r'^[>\-\*\+]\s+', '', st)
        st = re.sub(r'^\d+\.\s+', '', st)
        buf.append(st)
    if buf:
        out.append(' '.join(buf))
    return out


def section_prose(section):
    if section in _SECTION_PROSE_CACHE:
        return _SECTION_PROSE_CACHE[section]
    f = _section_file(section)
    paras = []
    if f and os.path.exists(f):
        paras = _strip_to_prose(open(f, encoding='utf-8').read())
    _SECTION_PROSE_CACHE[section] = paras
    return paras


# ---------------------------------------------------------------- anchoring
_WORD_RE = re.compile(r"\S+")


def _windows(text, min_w=MIN_WORDS, max_w=MAX_WORDS):
    """Yield contiguous word-windows of `text`, longest (up to max_w) first, so the
    most specific phrase is tried before shorter ones."""
    words = _WORD_RE.findall(text)
    for size in range(min(max_w, len(words)), min_w - 1, -1):
        for i in range(0, len(words) - size + 1):
            yield ' '.join(words[i:i + size])


def _subwindows_of(phrase, min_w=MIN_WORDS):
    """Word-windows of an existing phrase, longest first (preserve the author's spot)."""
    words = _WORD_RE.findall(phrase or '')
    for size in range(len(words), min_w - 1, -1):
        for i in range(0, len(words) - size + 1):
            yield ' '.join(words[i:i + size])


def term_variants(term):
    """Search strings for a headword: the term, comma-flipped ('Cheung, Vincent' ->
    'Vincent Cheung'), the surname/last token, plus lowercase forms. Distinctive,
    multi-word variants first."""
    out = []
    t = term.strip()
    def add(x):
        x = x.strip()
        if x and x not in out:
            out.append(x)
    add(t)
    if ',' in t:
        a, b = t.split(',', 1)
        add((b.strip() + ' ' + a.strip()))
        add(a.strip())                 # surname alone
    # drop parenthetical qualifiers
    add(re.sub(r'\s*\([^)]*\)', '', t).strip())
    return out


def resolves_in_all(phrase, section, editions):
    """True iff `phrase` resolves in-section in EVERY edition. editions: list of
    (norm_pages, ranges)."""
    if not phrase:
        return False
    return all(phrase_resolves(phrase, section, np, rg) for np, rg in editions)


def free_anchor_multi(term, section, old_phrase, editions, exclude=None):
    """Like free_anchor, but a candidate is accepted only if it resolves in-section in
    ALL editions (7x10 + 6x9 + 8.5x11). Body prose is identical across trims, so a
    short prose phrase that survives every trim's line-wrapping is the robust anchor.
    Returns the phrase or None."""
    exclude = exclude or set()
    cands = []
    for w in _subwindows_of(old_phrase):
        cands.append(w)
    variants = [index_anchors._norm(v) for v in term_variants(term)]
    variants = [v for v in variants if len(v) >= 3]
    for para in section_prose(section):
        np = index_anchors._norm(para)
        if not any(v in np for v in variants):
            continue
        for w in _windows(para):
            cands.append(w)
    for w in cands:
        nw = index_anchors._norm(w)
        if len(nw) < 8 or nw in exclude:
            continue
        if resolves_in_all(w, section, editions):
            return w
    return None


def _gnorm_term(term):
    """Loose term key for cross-index matching: lowercase, strip punctuation, drop a
    trailing parenthetical, flip 'Last, First' to 'first last'."""
    t = re.sub(r'\s*\([^)]*\)', '', term or '').strip()
    if ',' in t:
        a, b = t.split(',', 1)
        t = (b.strip() + ' ' + a.strip())
    return re.sub(r'[^a-z0-9 ]', '', t.lower()).strip()


def build_topical_borrow_map(topical_entries, norm_pages, ranges):
    """(_gnorm_term(term), section) -> a phrase from the topical index that RESOLVES
    in-section. Lets the glossary borrow the topical index's precise anchors for the
    same concept+section, free of AI. Prefers shorter resolving phrases."""
    bm = {}
    for e in topical_entries:
        key_t = _gnorm_term(e['term'])
        for loc in e.get('locations', []):
            sec = loc.get('section', '')
            ph = loc.get('phrase', '') or ''
            if not phrase_resolves(ph, sec, norm_pages, ranges):
                continue
            for kt in {key_t, _gnorm_term(e.get('sub', '') or '')} - {''}:
                k = (kt, sec)
                if k not in bm or len(ph) < len(bm[k]):
                    bm[k] = ph
    return bm


def borrow_anchor(term, section, borrow_map):
    """A topical phrase for the same concept+section, or None."""
    return borrow_map.get((_gnorm_term(term), section))


def free_anchor(term, section, old_phrase, norm_pages, ranges, exclude=None):
    """Return a NEW in-section anchor phrase (verbatim from old phrase or section
    source), validated to resolve in-section, or None if nothing free works.
    `exclude`: a set of normalized phrases already used for this section (avoid
    collapsing many headwords onto one identical anchor when avoidable)."""
    exclude = exclude or set()

    # 1) Salvage a window of the curated phrase (keeps the author's spot).
    for w in _subwindows_of(old_phrase):
        nw = index_anchors._norm(w)
        if len(nw) < 8 or nw in exclude:
            continue
        if in_section_page(nw, section, norm_pages, ranges):
            return w

    # 2) Prose window from the section source around a headword occurrence.
    variants = [index_anchors._norm(v) for v in term_variants(term)]
    variants = [v for v in variants if len(v) >= 3]
    best = None
    for para in section_prose(section):
        np = index_anchors._norm(para)
        if not any(v in np for v in variants):
            continue
        # try windows of this paragraph that CONTAIN a term variant, longest first
        for w in _windows(para):
            nw = index_anchors._norm(w)
            if len(nw) < 8 or nw in exclude:
                continue
            if not any(v in nw for v in variants):
                continue
            if in_section_page(nw, section, norm_pages, ranges):
                return w
        # fallback within this para: any resolving window even if it doesn't contain
        # the variant (the variant may be a pronoun-resolved concept) -- only if we
        # found the variant in this para, so we're still at the discussion spot.
        if best is None:
            for w in _windows(para):
                nw = index_anchors._norm(w)
                if len(nw) < 8 or nw in exclude:
                    continue
                if in_section_page(nw, section, norm_pages, ranges):
                    best = w
                    break
    return best
