#!/usr/bin/env python3
"""Drive the free re-anchoring pass over glossary + topical indexes.

For every locator that does NOT resolve in-section, try free_anchor (sub-window of the
curated phrase, then a prose window from the section source). If it yields a validated
in-section phrase, rewrite the locator's phrase in place. Locators still failing after
the free pass are written to a residue work-list for the AI fan-out.

Usage:
  python3 scripts/reanchor_run.py [--pdf PDF] [--apply] [--residue PATH]
Without --apply it's a dry run (reports counts, writes residue, touches no JSON).
"""
import os
import re
import sys
import json
import argparse
import shutil

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_anchors
import classify_index_anchors as C
import reanchor_lib as R

GLOSSARY_JSON = C.GLOSSARY_JSON
TOPICAL_JSON = C.TOPICAL_JSON


def process(label, path, norm_pages, ranges, apply_changes, borrow_map=None):
    entries = json.load(open(path, encoding='utf-8'))
    rec_free = rec_borrow = 0
    residue = []        # {index, section, term, old_phrase}
    # per-section set of normalized phrases already in use, to spread anchors out
    used = {}
    for e in entries:
        for loc in e.get('locations', []):
            ph = loc.get('phrase', '') or ''
            sec = loc.get('section', '')
            if R.phrase_resolves(ph, sec, norm_pages, ranges):
                used.setdefault(sec, set()).add(index_anchors._norm(ph))
                continue
            # 1) free anchor: sub-window of curated phrase, then section-source window
            new = R.free_anchor(e['term'], sec, ph, norm_pages, ranges, exclude=used.get(sec))
            src = 'free'
            # 2) borrow a matching topical phrase (glossary only)
            if not new and borrow_map is not None:
                cand = R.borrow_anchor(e['term'], sec, borrow_map)
                if cand and R.phrase_resolves(cand, sec, norm_pages, ranges):
                    new, src = cand, 'borrow'
            if new:
                if apply_changes:
                    loc['phrase'] = new
                used.setdefault(sec, set()).add(index_anchors._norm(new))
                if src == 'free':
                    rec_free += 1
                else:
                    rec_borrow += 1
            else:
                residue.append({'index': label, 'section': sec,
                                'term': e['term'], 'old_phrase': ph})
    if apply_changes:
        shutil.copyfile(path, path + '.precision-bak')
        json.dump(entries, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return rec_free, rec_borrow, residue, entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', default=C.DEFAULT_PDF)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--residue', default=os.path.join(R.BOOK_DIR, 'index-data', 'reanchor-residue.json'))
    args = ap.parse_args()

    print(f"Loading {args.pdf} ...", file=sys.stderr)
    norm_pages, ranges = R.load_pdf(args.pdf)

    # Build the topical borrow map FIRST (from the topical index as it currently
    # stands -- if topical is processed with --apply, do it before glossary so the
    # glossary borrows the freshly-anchored phrases).
    all_residue = []
    # Process topical first so glossary can borrow.
    order = [('Topical', TOPICAL_JSON), ('Glossary', GLOSSARY_JSON)]
    borrow_map = None
    for label, path in order:
        if label == 'Glossary':
            topical_now = json.load(open(TOPICAL_JSON, encoding='utf-8'))
            print("Building topical borrow map ...", file=sys.stderr)
            borrow_map = R.build_topical_borrow_map(topical_now, norm_pages, ranges)
            print(f"  borrow map: {len(borrow_map)} (term,section) keys", file=sys.stderr)
        rf, rb, res, _ = process(label, path, norm_pages, ranges, args.apply, borrow_map=borrow_map)
        total = sum(len(e.get('locations', [])) for e in json.load(open(path, encoding='utf-8')))
        print(f"{label}: recovered {rf} free + {rb} borrow; {len(res)} residue (AI) of {total} "
              f"locators ({'APPLIED' if args.apply else 'dry-run'})")
        all_residue.extend(res)

    json.dump(all_residue, open(args.residue, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    # summarize residue by section
    from collections import Counter
    by_sec = Counter((r['index'], r['section']) for r in all_residue)
    print(f"\nResidue total: {len(all_residue)} -> {args.residue}")
    for (idx, sec), n in sorted(by_sec.items(), key=lambda kv: -kv[1])[:25]:
        print(f"  {n:>4}  {idx:<9} {sec}")


if __name__ == '__main__':
    main()
