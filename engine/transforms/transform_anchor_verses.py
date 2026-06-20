#!/usr/bin/env python3
"""
Web-only: when one of THE SENTENCE's four anchor verses is quoted inline, tag
the containing <p> as a scripture-anchor callout so CSS can render it with a
distinctive frame and a "1 of 4" badge tying that quote back to the spine of
the book.

Anchor verses (from Chapter 1's derivation):
  1  Hebrews 11:3
  2  Colossians 1:17
  3  Acts 17:28
  4  Isaiah 45:7
"""
import os
import re
import sys
import glob


# (number, label, regex). The regex matches typical inline-citation forms used
# in the book: "(Heb. 11:3)" / "(Heb 11:3)" / "Hebrews 11:3" with optional period.
ANCHORS = [
    (1, 'Hebrews 11:3',     re.compile(r'\(?\bHeb(?:rews|\.)?\s*11:3\b\)?')),
    (2, 'Colossians 1:17',  re.compile(r'\(?\bCol(?:ossians|\.)?\s*1:17\b\)?')),
    (3, 'Acts 17:28',       re.compile(r'\(?\bActs\s*17:28\b\)?')),
    (4, 'Isaiah 45:7',      re.compile(r'\(?\bIsa(?:iah|\.)?\s*45:7\b\)?')),
]

# Match each <p>...</p> whose body looks like an italic scripture quote.
# Pandoc renders straight quotes as curly (“ ”), so accept either form.
PARA_RE = re.compile(r'<p>\s*(<em>[^<]*["“][^<]*["”][^<]*</em>.*?)</p>', re.DOTALL)


def add_class_to_p(p_tag_with_body, cls, badge):
    # Convert a `<p>BODY</p>` segment into `<p class="cls">BODY</p>` (or merge
    # into existing class). Plus prepend the badge span inside the <p>.
    badge_html = (
        f'<span class="anchor-verse-badge" aria-hidden="true">'
        f'<span class="anchor-verse-badge-num">{badge[0]}</span>'
        f'<span class="anchor-verse-badge-of">of 4</span>'
        f'</span>'
    )
    # p_tag_with_body is the inner HTML of the <p>; we re-wrap with class.
    return badge_html + p_tag_with_body


def transform_one(html):
    """Walk paragraphs, detect anchor refs, add class + badge. Return (html, count)."""
    if 'anchor-verse-callout' in html:
        return html, 0
    count = 0
    out = []
    cursor = 0
    for m in PARA_RE.finditer(html):
        body = m.group(1)
        # Skip if this <p> already has a class attribute (would be e.g. costume-field).
        # We only convert plain <p>...</p> here.
        # Find which (if any) anchor matches.
        match_idx = None
        match_label = None
        for n, label, rx in ANCHORS:
            if rx.search(body):
                match_idx = n
                match_label = label
                break
        if match_idx is None:
            continue
        out.append(html[cursor:m.start()])
        new_body = add_class_to_p(body, 'anchor-verse-callout', (match_idx, match_label))
        out.append(
            f'<p class="anchor-verse-callout anchor-verse-callout-{match_idx}" data-anchor-verse="{match_label}">'
            f'{new_body}</p>'
        )
        cursor = m.end()
        count += 1
    out.append(html[cursor:])
    return ''.join(out), count


def transform(chapters_dir):
    total = 0
    files = 0
    for path in sorted(glob.glob(os.path.join(chapters_dir, '*.html'))):
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        new_html, n = transform_one(html)
        if n > 0:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_html)
            total += n
            files += 1
    print(f' done ({total} anchor-verse callouts across {files} files)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
