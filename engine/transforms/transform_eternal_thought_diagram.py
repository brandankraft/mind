#!/usr/bin/env python3
"""
Web-only: replace the ASCII tree diagram of "THE ETERNAL THOUGHT -> Cross /
Conversion / Judgment" in chapter-02.html with a styled card layout.
PDF/EPUB keep the ASCII art untouched.
"""
import os
import re
import sys


PARTIAL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'templates', 'eternal_thought_diagram_partial.html',
)


def load_partial():
    with open(PARTIAL_PATH, 'r', encoding='utf-8') as f:
        return f.read().strip()


PATTERN = re.compile(r'<pre><code>\s*THE ETERNAL THOUGHT.*?</code></pre>', re.DOTALL)


def transform_html(html):
    """Swap the eternal-thought ASCII block for the styled partial. Returns (html, n)."""
    if 'eternal-thought-diagram' in html:
        return html, 0
    return PATTERN.subn(lambda m: load_partial(), html, count=1)


def transform(chapters_dir):
    path = os.path.join(chapters_dir, 'chapter-02.html')
    if not os.path.isfile(path):
        print('  chapter-02.html not found', file=sys.stderr)
        return
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    new_html, n = transform_html(html)
    if n == 0:
        print('  eternal thought <pre><code> block not found (or already done)', file=sys.stderr)
        return
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(' done (eternal thought diagram transformed)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
