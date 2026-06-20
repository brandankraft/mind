#!/usr/bin/env python3
"""
Web-only: replace the Plato -> Augustine -> Western Tradition -> This Book
lineage <pre><code> block in appendix-i.html with a styled vertical timeline
of cards. PDF/EPUB keep the ASCII art untouched.
"""
import os
import re
import sys


# Single source of truth for the lineage diagram HTML. Same partial is included
# in book_template.php (/mind About) and book_search_modal.php (Mind modal About),
# and pasted into about.html (static chapter front matter).
PARTIAL_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', 'public_html', 'templates', 'lineage_diagram_partial.html',
)


def load_partial():
    with open(PARTIAL_PATH, 'r', encoding='utf-8') as f:
        return f.read().strip()


# Match the specific <pre><code>...PLATO...AUGUSTINE...THIS BOOK...</code></pre>
# block. Anchored by the unique "PLATO  (4th c. BC)" header.
PATTERN = re.compile(r'<pre><code>PLATO\s+\(4th c\. BC\).*?</code></pre>', re.DOTALL)


def transform_html(html):
    """Swap the lineage ASCII block for the styled partial. Returns (html, n).
    Reusable on any HTML string -- the web file-walker and the PDF pipeline."""
    if 'lineage-diagram' in html:
        return html, 0
    return PATTERN.subn(lambda m: load_partial(), html, count=1)


def transform(chapters_dir):
    path = os.path.join(chapters_dir, 'appendix-i.html')
    if not os.path.isfile(path):
        print('  appendix-i.html not found', file=sys.stderr)
        return
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    new_html, n = transform_html(html)
    if n == 0:
        print('  lineage <pre><code> block not found (or already done)', file=sys.stderr)
        return
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(' done (lineage diagram transformed)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
