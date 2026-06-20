#!/usr/bin/env python3
"""Cross-edition hardening: ensure every locator resolves in-section in ALL THREE
printed trims (7x10, 6x9, 8.5x11). For any locator that fails in any edition, find a
phrase (sub-window of the current one, or a section-source prose window) that resolves
in-section in EVERY edition. Falls back to keeping the current phrase when no common
phrase exists (honest right-chapter section-start in the failing trim).

Usage: python3 scripts/reanchor_harden.py [--apply]
"""
import os
import sys
import json
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_anchors
import classify_index_anchors as C
import reanchor_lib as R

BOOK = os.path.join(R.BOOK_DIR, 'ingramspark')
PDFS = [
    os.path.join(BOOK, 'A-Thought-in-the-Mind-of-God-7x10.pdf'),
    os.path.join(BOOK, 'A-Thought-in-the-Mind-of-God-6x9.pdf'),
    os.path.join(BOOK, 'A-Thought-in-the-Mind-of-God-8.5x11-hardcover.pdf'),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()

    editions = []
    for p in PDFS:
        print(f"Loading {os.path.basename(p)} ...", file=sys.stderr)
        editions.append(R.load_pdf(p))

    for label, path in [('Topical', C.TOPICAL_JSON), ('Glossary', C.GLOSSARY_JSON)]:
        entries = json.load(open(path, encoding='utf-8'))
        fixed = stuck = 0
        used = {}
        for e in entries:
            for loc in e.get('locations', []):
                ph = loc.get('phrase', '') or ''
                sec = loc.get('section', '')
                if R.resolves_in_all(ph, sec, editions):
                    used.setdefault(sec, set()).add(index_anchors._norm(ph))
                    continue
                new = R.free_anchor_multi(e['term'], sec, ph, editions, exclude=used.get(sec))
                if new:
                    if args.apply:
                        loc['phrase'] = new
                    used.setdefault(sec, set()).add(index_anchors._norm(new))
                    fixed += 1
                else:
                    stuck += 1
        if args.apply:
            shutil.copyfile(path, path + '.harden-bak')
            json.dump(entries, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"{label}: hardened {fixed}; still trim-specific {stuck} "
              f"({'APPLIED' if args.apply else 'dry-run'})")


if __name__ == '__main__':
    main()
