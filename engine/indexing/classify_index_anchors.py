#!/usr/bin/env python3
"""Classify every glossary + topical-index locator against a RENDERED book PDF.

For each locator (a {phrase, section} pair) report which bucket it falls in:

  in_section    - phrase resolves to a page INSIDE its own chapter/appendix range (CORRECT)
  out_of_section- phrase is found, but only OUTSIDE its section (WRONG chapter -- the resolver bug)
  section_start - phrase not found anywhere in its section (falls back to the section's first page)
  no_range      - the section label didn't map to a known range (should be ~0; a data bug)

This mirrors build-book-pdf.py's build_section_ranges / _seckey / _resolve_page exactly
so the buckets predict what the PDF builder will actually print. Targets for the
index-precision project: out_of_section == 0 AND section_start == 0 for BOTH indexes.

Usage:
  python3 scripts/classify_index_anchors.py [PDF] [--list out_of_section|section_start] [--index glossary|topical|both]

Default PDF: ~/Anna/Mind/ingramspark/A-Thought-in-the-Mind-of-God-7x10.pdf
"""
import os
import re
import sys
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_anchors

HOME = os.path.expanduser('~')
BOOK_DIR = os.path.join(HOME, 'Anna', 'Mind')
DEFAULT_PDF = os.path.join(BOOK_DIR, 'ingramspark', 'A-Thought-in-the-Mind-of-God-7x10.pdf')
GLOSSARY_JSON = os.path.join(BOOK_DIR, 'index-data', 'glossary-index.json')
TOPICAL_JSON = os.path.join(BOOK_DIR, 'index-data', 'topical-index.json')


def build_page_cache(pdf_path):
    """Return [(page_number, normalized_text)] for each page. Page number is the PDF's
    PageLabel when present (so a web-PDF whose cover shifts the physical sequence still
    reports CONTENT page numbers -- the same space the index "(p. N)" refs live in),
    else physical pidx+1. Non-numeric labels (cover/back cover) get descending negatives
    so they never fall inside a content page range."""
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    try:
        labels = reader.page_labels
    except Exception:
        labels = None
    out, neg = [], 0
    for pidx in range(len(reader.pages)):
        text = re.sub(r'\s+', ' ', (reader.pages[pidx].extract_text() or ""))
        lab = labels[pidx] if labels and pidx < len(labels) else str(pidx + 1)
        if lab.isdigit():
            num = int(lab)
        else:
            neg -= 1
            num = neg
        out.append((num, text))
    return out


def find_backmatter_start(pages):
    heads = ("Scripture Index", "Topical Index", "Glossary", "Bibliography")
    for printed, raw in pages:
        body = raw.lstrip()
        if any(body.startswith(h) for h in heads):
            return printed
    return 999999


_APX_REF_RE = re.compile(r'Appendix ([A-Z]\d*):[^(\n]*?\(p\.\s*(\d+)\)')
_CALLOUT_RE = re.compile(r'^.{0,90}?\(p\.\s*\d+\)')


def build_section_ranges(pages, index_start):
    """Printed [start,end) page range for every chapter/appendix/front-matter section.

    Appendix openings are taken from the book's OWN cross-reference lines
    ("Appendix A6: Eschatology (p. 524)") -- authoritative and immune to the
    Related-Appendices callouts and the detailed-appendix-contents pages that ALSO
    start with "Appendix X:" but are NOT the real opening (these gave A6 a bogus
    1-page range at p.182 and falsely flagged ~1500 locators as out-of-section).
    Chapters / front-matter use a startswith scan that skips any page whose first
    ~90 chars contain a "(p. N)" ref (i.e. a callout/contents line)."""
    apx_auth = {}
    for printed, raw in pages:
        for m in _APX_REF_RE.finditer(raw):
            apx_auth.setdefault('App. ' + m.group(1).upper(), int(m.group(2)))

    targets = {'Prologue': 'Prologue', 'Preface': 'Preface', 'Epilogue': 'Epilogue',
               'Afterword': 'Afterword', 'How This Book Talks': 'How This Book Talks',
               'Acknowledgments': 'Acknowledgments'}
    for i in range(1, 31):
        targets[f'Ch. {i}'] = f'Chapter {i}:'
    for n in range(1, 13):
        targets[f'App. A{n}'] = f'Appendix A{n}:'
    for letter in 'bcdefghijklmnopqrs':
        targets[f'App. {letter.upper()}'] = f'Appendix {letter.upper()}:'
    targets['App. P'] = 'Appendix P:'
    targets['App. Q'] = 'Appendix Q:'
    starts = {}
    remaining = dict(targets)
    for printed, raw in pages:
        body = raw.lstrip()
        if 'Dedication' not in starts and body.startswith('To my son'):
            starts['Dedication'] = printed
        if 'Table of Contents' not in starts and 'Table of Contents' in body[:300]:
            starts['Table of Contents'] = printed
        if _CALLOUT_RE.match(body):          # callout / detailed-contents line -> not a real opening
            continue
        for lab, st in list(remaining.items()):
            if body.startswith(st):
                starts[lab] = printed
                del remaining[lab]
    starts.update(apx_auth)                   # authoritative appendix openings win
    idx_cap = min(starts.get('App. P', index_start), starts.get('App. Q', index_start), index_start)
    ordered = sorted((p, lab) for lab, p in starts.items())
    ranges = {}
    for i, (p, lab) in enumerate(ordered):
        end = ordered[i + 1][0] if i + 1 < len(ordered) else idx_cap
        ranges[lab] = (p, end)
    return starts, ranges, idx_cap


def seckey(section):
    m = re.match(r'Chapter (\d+)', section or '')
    if m:
        return f"Ch. {m.group(1)}"
    m = re.match(r'Appendix ([A-Za-z]\d*)', section or '')
    if m:
        return f"App. {m.group(1).upper()}"
    return section or ''


def make_classifier(norm_pages, ranges):
    def classify(phrase, section):
        rng = ranges.get(seckey(section))
        if rng is None:
            return 'no_range'
        if not phrase or not index_anchors._norm(phrase):
            return 'section_start'   # null/blank locator -> honest section-start
        found_anywhere = False
        for ph in index_anchors.phrase_candidates(phrase):
            for p, t in norm_pages:
                if ph in t:
                    if rng[0] <= p < rng[1]:
                        return 'in_section'
                    found_anywhere = True
        return 'out_of_section' if found_anywhere else 'section_start'
    return classify


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf', nargs='?', default=DEFAULT_PDF)
    ap.add_argument('--list', choices=['out_of_section', 'section_start', 'no_range'], default=None,
                    help='print every locator in this bucket')
    ap.add_argument('--index', choices=['glossary', 'topical', 'both'], default='both')
    ap.add_argument('--json-out', default=None, help='write per-locator buckets to a JSON file')
    args = ap.parse_args()

    print(f"Reading {args.pdf} ...", file=sys.stderr)
    pages = build_page_cache(args.pdf)
    bm = find_backmatter_start(pages)
    starts, ranges, idx_cap = build_section_ranges(pages, bm)
    print(f"{len(pages)} pages; backmatter starts p.{idx_cap}; {len(ranges)} sections mapped",
          file=sys.stderr)
    norm_pages = [(p, index_anchors._norm(t)) for p, t in pages]
    classify = make_classifier(norm_pages, ranges)

    indexes = []
    if args.index in ('glossary', 'both'):
        indexes.append(('Glossary', GLOSSARY_JSON))
    if args.index in ('topical', 'both'):
        indexes.append(('Topical', TOPICAL_JSON))

    out_records = {}
    print(f"\n{'Index':<10} {'Total':>7} {'In-section':>12} {'Out-of-sec':>12} {'Sec-start':>11} {'No-range':>9}")
    print('-' * 64)
    for label, path in indexes:
        entries = json.load(open(path, encoding='utf-8'))
        counts = {'in_section': 0, 'out_of_section': 0, 'section_start': 0, 'no_range': 0}
        listed = []
        recs = []
        for e in entries:
            for loc in e.get('locations', []):
                b = classify(loc.get('phrase', ''), loc.get('section', ''))
                counts[b] += 1
                recs.append({'term': e['term'], 'phrase': loc.get('phrase', ''),
                             'section': loc.get('section', ''), 'bucket': b})
                if args.list and b == args.list:
                    listed.append((e['term'], loc.get('section', ''), loc.get('phrase', '')))
        total = sum(counts.values())
        pct = lambda n: f"{n} ({round(100*n/total)}%)" if total else str(n)
        print(f"{label:<10} {total:>7} {pct(counts['in_section']):>12} "
              f"{pct(counts['out_of_section']):>12} {pct(counts['section_start']):>11} "
              f"{counts['no_range']:>9}")
        out_records[label] = recs
        if args.list and listed:
            print(f"\n--- {label}: {len(listed)} {args.list} ---", file=sys.stderr)
            for term, sec, ph in listed:
                print(f"  [{sec}] {term}: {ph!r}", file=sys.stderr)

    if args.json_out:
        json.dump(out_records, open(args.json_out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"\nWrote per-locator buckets to {args.json_out}", file=sys.stderr)


if __name__ == '__main__':
    main()
