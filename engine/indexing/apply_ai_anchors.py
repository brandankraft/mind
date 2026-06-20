#!/usr/bin/env python3
"""Validate AI-returned anchor phrases against the rendered PDF and patch the indexes.

Reads /tmp/reanchor_work/out/*.json (each: {section, results:[{term, old_phrase,
phrase, note}]}), validates every non-null phrase resolves IN-SECTION against the 7x10
PDF, and patches the matching locator in glossary-index.json / topical-index.json
(matched by term + section + old_phrase). Phrases that fail validation -> retry list.
Phrases the AI returned null for (concept genuinely absent) -> reported, left as
section-start.

Usage: python3 scripts/apply_ai_anchors.py [--apply] [--retry PATH]
"""
import os
import re
import sys
import json
import glob
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_anchors
import classify_index_anchors as C
import reanchor_lib as R

OUT_DIR = '/tmp/reanchor_work/out'


def load_ai_results(out_dir=OUT_DIR):
    rows = []
    for f in glob.glob(os.path.join(out_dir, '*.json')):
        try:
            d = json.load(open(f, encoding='utf-8'))
        except Exception as e:
            print(f"  bad json {f}: {e}", file=sys.stderr); continue
        sec = d.get('section', '')
        for r in d.get('results', []):
            rows.append({'section': sec, 'term': r.get('term', ''),
                         'old_phrase': r.get('old_phrase', '') or '',
                         'phrase': r.get('phrase'), 'note': r.get('note', '')})
    return rows


def patch_index(path, patches, apply_changes):
    """patches: dict (term, section, old_phrase) -> new_phrase. Returns (n_applied, unmatched)."""
    entries = json.load(open(path, encoding='utf-8'))
    applied = 0
    used = set()
    for e in entries:
        for loc in e.get('locations', []):
            key = (e['term'], loc.get('section', ''), loc.get('phrase', '') or '')
            if key in patches and id(loc) not in used:
                if apply_changes:
                    loc['phrase'] = patches[key]
                used.add(id(loc))
                applied += 1
    if apply_changes:
        shutil.copyfile(path, path + '.ai-bak')
        json.dump(entries, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    unmatched = [k for k in patches if k not in
                 {(e['term'], l.get('section', ''), l.get('phrase', '') or '')
                  for e in entries for l in e.get('locations', [])}]
    return applied, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', default=C.DEFAULT_PDF)
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--out-dir', default=OUT_DIR)
    ap.add_argument('--retry', default='/tmp/reanchor_work/retry.json')
    args = ap.parse_args()

    print(f"Loading {args.pdf} ...", file=sys.stderr)
    norm_pages, ranges = R.load_pdf(args.pdf)
    rows = load_ai_results(args.out_dir)
    print(f"Loaded {len(rows)} AI results from {len(glob.glob(args.out_dir + '/*.json'))} files")

    valid, failed, absent = {}, [], []
    for r in rows:
        ph = r['phrase']
        if not ph:
            absent.append(r); continue
        if R.phrase_resolves(ph, r['section'], norm_pages, ranges):
            valid[(r['term'], r['section'], r['old_phrase'])] = ph
        else:
            failed.append(r)

    print(f"Validated in-section: {len(valid)}   failed-validation: {len(failed)}   "
          f"AI-says-absent: {len(absent)}")

    # split patches by which index each term/section belongs to -- apply to both files;
    # patch_index only matches locators that actually exist there.
    gl_applied, gl_un = patch_index(C.GLOSSARY_JSON, valid, args.apply)
    tp_applied, tp_un = patch_index(C.TOPICAL_JSON, valid, args.apply)
    print(f"Patched: glossary {gl_applied}, topical {tp_applied} "
          f"({'APPLIED' if args.apply else 'dry-run'})")
    truly_unmatched = set(gl_un) & set(tp_un)
    if truly_unmatched:
        print(f"WARNING: {len(truly_unmatched)} validated phrases matched no locator "
              f"(term/section/old_phrase mismatch):", file=sys.stderr)
        for k in list(truly_unmatched)[:15]:
            print(f"  {k}", file=sys.stderr)

    json.dump({'failed': failed, 'absent': absent}, open(args.retry, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f"Wrote retry/absent -> {args.retry}")
    if failed:
        from collections import Counter
        print("Failed-validation by section:", dict(Counter(r['section'] for r in failed)))


if __name__ == '__main__':
    main()
