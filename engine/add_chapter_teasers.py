#!/usr/bin/env python3
"""
Post-processor that extracts the first sentence of each chapter's body and
writes it into chapters.json as a `teaser` field. The chapter template uses
this to render a "Next: Chapter X -- Title" card at the bottom of each
chapter with a teaser pulled from the next chapter's first sentence.

Skips virtual entries (no file). Trims teasers to ~180 chars at sentence
boundary.
"""
import json
import os
import re
import sys


MAX_TEASER_LEN = 180

# Strip these structural blocks before sentence extraction; their first text
# isn't a useful teaser.
STRIP_TAGS = [
    'style', 'script',  # drop inline CSS/JS bodies (e.g. the title page's @font-face)
    'aside', 'figure', 'pre', 'blockquote', 'h1', 'h2', 'h3', 'h4',
    'div', 'ol', 'ul', 'table',
]


def strip_html(html):
    # Drop entire structural blocks first.
    for tag in STRIP_TAGS:
        html = re.sub(rf'<{tag}\b[^>]*>.*?</{tag}\s*>', ' ', html, flags=re.IGNORECASE | re.DOTALL)
    # Remove all remaining tags.
    text = re.sub(r'<[^>]+>', ' ', html)
    # Normalize whitespace and decode some common entities.
    text = (text.replace('&nbsp;', ' ')
                 .replace('&amp;', '&')
                 .replace('&quot;', '"')
                 .replace('&#39;', "'")
                 .replace('&lsquo;', '‘')
                 .replace('&rsquo;', '’')
                 .replace('&ldquo;', '“')
                 .replace('&rdquo;', '”')
                 .replace('&mdash;', '—')
                 .replace('&ndash;', '–'))
    return re.sub(r'\s+', ' ', text).strip()


def extract_teaser(html):
    text = strip_html(html)
    if not text:
        return ''
    # Sentence boundary: look for the first ". ", "! ", "? " that isn't an
    # abbreviation. Simple heuristic: split on sentence terminators followed
    # by space + capital.
    m = re.search(r'(.+?[\.!?])\s+(?=[A-Z“"])', text)
    sentence = m.group(1) if m else text
    if len(sentence) > MAX_TEASER_LEN:
        # Hard-cut at last word boundary before MAX_TEASER_LEN.
        cut = sentence[:MAX_TEASER_LEN].rsplit(' ', 1)[0]
        sentence = cut.rstrip(',;:') + '…'
    return sentence


def main():
    if len(sys.argv) < 2:
        print('Usage: add_chapter_teasers.py <output_dir>', file=sys.stderr)
        sys.exit(1)

    output_dir = sys.argv[1]
    chapters_json_path = os.path.join(output_dir, 'chapters.json')
    chapters_dir = os.path.join(output_dir, 'chapters')

    with open(chapters_json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    for chap in data.get('chapters', []):
        file_name = chap.get('file')
        if not file_name:
            continue
        path = os.path.join(chapters_dir, file_name)
        if not os.path.isfile(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        teaser = extract_teaser(html)
        if teaser:
            chap['teaser'] = teaser
            count += 1

    with open(chapters_json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')

    print(f' done ({count} teasers extracted)')


if __name__ == '__main__':
    main()
