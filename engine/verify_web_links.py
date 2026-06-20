#!/usr/bin/env python3
"""Verify the WEB build's glossary + topical-index deep links resolve.

For appendix-r.html (glossary) and appendix-q.html (topical index): every
/mind/chapter/<slug>#<anchor> link must point to an anchor id that actually exists in
the target chapter file. Exit 0 if all resolve.

Usage: verify_web_links.py [chapters_dir]
"""
import os
import re
import sys

CH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'public_html', 'book-content', 'chapters')


def slug_to_file(slug):
    if slug.isdigit():
        return f'chapter-{int(slug):02d}.html'
    return f'{slug}.html'


def ids_in(fname):
    p = os.path.join(CH, fname)
    if not os.path.exists(p):
        return None
    return set(re.findall(r'id="([^"]+)"', open(p, encoding='utf-8').read()))


def check_file(fname, anchor_prefix):
    p = os.path.join(CH, fname)
    if not os.path.exists(p):
        print(f"  [FAIL] {fname} missing"); return False
    html = open(p, encoding='utf-8').read()
    links = re.findall(r'href="/mind/chapter/([^"#]+)#(' + anchor_prefix + r'-[^"]+)"', html)
    bad = []
    cache = {}
    for slug, anc in links:
        f = slug_to_file(slug)
        if f not in cache:
            cache[f] = ids_in(f)
        if cache[f] is None or anc not in cache[f]:
            bad.append((slug, anc))
    ok = len(links) > 0 and not bad
    print(f"  [{'PASS' if ok else 'FAIL'}] {fname}: {len(links)} {anchor_prefix} links, {len(bad)} broken"
          + (f" e.g. {bad[:3]}" if bad else ""))
    return ok


if __name__ == '__main__':
    print("=== WEB deep-link resolution ===")
    a = check_file('appendix-r.html', 'glx')      # glossary
    b = check_file('appendix-q.html', 'ix')        # topical index
    sys.exit(0 if (a and b) else 1)
