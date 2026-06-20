#!/usr/bin/env python3
"""
Web-only: replace the file-tree ASCII diagram in how-this-book-talks.html
with a styled "code editor sidebar" treatment that owns the book-as-codebase
metaphor visually. PDF/EPUB keep the ASCII tree untouched.
"""
import os
import re
import sys


PARTIAL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'public_html', 'templates', 'book_tree_diagram_partial.html',
)


def load_partial():
    with open(PARTIAL_PATH, 'r', encoding='utf-8') as f:
        return f.read().strip()


# Match the <pre><code>...the-sentence...</code></pre> block. transform_code_blocks
# runs first and may have wrapped tokens in <span>s, so we anchor on the literal
# "the-sentence" text and the closing </pre>.
PATTERN = re.compile(r'<pre><code[^>]*>[^<]*the-sentence.*?</code></pre>', re.DOTALL)


def transform_html(html):
    """Swap the book-tree ASCII block for the styled partial. Returns (html, n)."""
    if 'book-tree' in html:
        return html, 0
    return PATTERN.subn(lambda m: load_partial(), html, count=1)


def transform(chapters_dir):
    path = os.path.join(chapters_dir, 'how-this-book-talks.html')
    if not os.path.isfile(path):
        print('  how-this-book-talks.html not found', file=sys.stderr)
        return
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    new_html, n = transform_html(html)
    if n == 0:
        print('  book tree <pre><code> block not found (or already done)', file=sys.stderr)
        return
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(' done (book tree transformed)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
