#!/usr/bin/env python3
"""
Post-processor that computes a word count and estimated reading time for every
chapter, then writes them into chapters.json so the chapter template can display
"~12 min read" under each chapter title.

Reading speed assumption: 230 words per minute (average adult silent reading
of nonfiction prose). Times are rounded up to the nearest whole minute, with a
minimum of 1.

Skips virtual parent entries (e.g. appendix-a) since they have no file of their
own. Their physical sub-chapters get individual estimates.

Runs as a build step from scripts/build-book.sh after split_appendix_a.py and
transform_cascades.py have done their work.
"""
import json
import math
import os
import re
import sys


WORDS_PER_MINUTE = 230


def clean_text_for_count(html):
    """Strip HTML tags, scripts, styles, comments. Return plain text."""
    block_tags = ['script', 'style', 'noscript', 'template', 'svg', 'iframe', 'object', 'embed']
    for tag in block_tags:
        html = re.sub(r'<' + tag + r'\b[^>]*>.*?</' + tag + r'\s*>', ' ', html, flags=re.IGNORECASE | re.DOTALL)
    html = re.sub(r'<!--.*?-->', ' ', html, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', ' ', html)
    return text


def count_words(text):
    """Approximate word count by splitting on whitespace runs."""
    text = re.sub(r'\s+', ' ', text).strip()
    if not text:
        return 0
    return len(text.split())


def main():
    if len(sys.argv) < 2:
        print("Usage: add_reading_times.py <output_dir>", file=sys.stderr)
        sys.exit(1)

    output_dir = sys.argv[1]
    chapters_dir = os.path.join(output_dir, 'chapters')
    manifest_path = os.path.join(output_dir, 'chapters.json')

    if not os.path.exists(manifest_path):
        print(f"ERROR: {manifest_path} not found", file=sys.stderr)
        sys.exit(1)

    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    chapters = data.get('chapters', [])
    updated = 0

    for ch in chapters:
        # Virtual parents have no file. Skip — but if they have physical children
        # via a "split" group (e.g. appendix-a), we'll fill them in below by aggregating.
        if ch.get('virtual') or not ch.get('file'):
            continue
        path = os.path.join(chapters_dir, ch['file'])
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        text = clean_text_for_count(html)
        words = count_words(text)
        minutes = max(1, math.ceil(words / WORDS_PER_MINUTE))
        ch['word_count'] = words
        ch['read_time_minutes'] = minutes
        updated += 1

    # Aggregate read time for virtual parents (e.g. appendix-a) by summing their
    # physical children. Lets the brain modal show a total for the whole grouping.
    for ch in chapters:
        if not ch.get('virtual'):
            continue
        # Find children whose slug starts with this slug + '-'
        prefix = ch['slug'] + '-'
        total_words = 0
        total_minutes = 0
        for child in chapters:
            if child.get('slug', '').startswith(prefix) and not child.get('virtual'):
                total_words += child.get('word_count', 0)
                total_minutes += child.get('read_time_minutes', 0)
        if total_words > 0:
            ch['word_count'] = total_words
            ch['read_time_minutes'] = total_minutes

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f"  reading times: {updated} chapters annotated")


if __name__ == '__main__':
    main()
