#!/usr/bin/env python3
"""
Web-only: replace the THE SENTENCE radial ASCII diagram in appendix-b.html
with a styled breakdown -- the full sentence as a centered quote followed
by five numbered clause cards. PDF/EPUB keep the ASCII art untouched.
"""
import os
import re
import sys


REPLACEMENT = """<div class="sentence-breakdown">

  <div class="sentence-breakdown-header">
    <span class="sb-label">The Sentence</span>
    <blockquote class="sb-quote">
      &ldquo;Everything that exists is a thought in the mind of God, sustained by His will, authored by His purpose, and held together by personal covenants of love.&rdquo;
    </blockquote>
  </div>

  <ol class="sb-clauses">

    <li class="sb-clause">
      <div class="sb-clause-num">1</div>
      <div class="sb-clause-body">
        <h4 class="sb-clause-text">&ldquo;Everything that exists&rdquo;</h4>
        <p class="sb-description">Universal scope. No exceptions.</p>
        <p class="sb-refs"><span class="sb-refs-label">Develops in:</span> Ch 5, 11, 13, 14, 19 &middot; App A1, A2, A8, A9, A12</p>
      </div>
    </li>

    <li class="sb-clause">
      <div class="sb-clause-num">2</div>
      <div class="sb-clause-body">
        <h4 class="sb-clause-text">&ldquo;is a thought in the mind of God&rdquo;</h4>
        <p class="sb-description">Reality is information. Mind precedes matter. Personal, triune Author.</p>
        <p class="sb-refs"><span class="sb-refs-label">Develops in:</span> Ch 1, 3, 4, 6, 10, 16, 17, 22, 28&ndash;29 &middot; App A1, A2, A4, A6, E, G, H, I, J, N, O</p>
      </div>
    </li>

    <li class="sb-clause">
      <div class="sb-clause-num">3</div>
      <div class="sb-clause-body">
        <h4 class="sb-clause-text">&ldquo;sustained by His will&rdquo;</h4>
        <p class="sb-description">Continuous sustaining. Active preservation. Rendered every moment.</p>
        <p class="sb-refs"><span class="sb-refs-label">Develops in:</span> Ch 2, 3, 4, 27 &middot; App A6, A8, G, H</p>
      </div>
    </li>

    <li class="sb-clause">
      <div class="sb-clause-num">4</div>
      <div class="sb-clause-body">
        <h4 class="sb-clause-text">&ldquo;authored by His purpose&rdquo;</h4>
        <p class="sb-description">Intentional design. Equal ultimacy. Two seeds.</p>
        <p class="sb-refs"><span class="sb-refs-label">Develops in:</span> Ch 5, 11, 12, 13, 14, 18, 19 &middot; App A3, A9, C, D, N</p>
      </div>
    </li>

    <li class="sb-clause sb-clause-last">
      <div class="sb-clause-num">5</div>
      <div class="sb-clause-body">
        <h4 class="sb-clause-text">&ldquo;held together by personal covenants of love&rdquo;</h4>
        <p class="sb-description">Covenants are promises, not contracts. The Author binds Himself. The elect held across the seam.</p>
        <p class="sb-refs"><span class="sb-refs-label">Develops in:</span> Ch 7&ndash;10, 15, 20&ndash;26, 30 &middot; App A5, A6, A7, A10, A11, K, L, M</p>
      </div>
    </li>

  </ol>

</div>"""


# Match the <pre><code>...THE SENTENCE...</code></pre> block, anchored by the
# unique "THE SENTENCE" header inside a <pre><code>.
PATTERN = re.compile(r'<pre><code>\s*THE SENTENCE.*?</code></pre>', re.DOTALL)


def transform_html(html):
    """Swap the sentence-breakdown ASCII block for the styled markup. Returns (html, n)."""
    if 'sentence-breakdown' in html:
        return html, 0
    return PATTERN.subn(lambda m: REPLACEMENT, html, count=1)


def transform(chapters_dir):
    path = os.path.join(chapters_dir, 'appendix-b.html')
    if not os.path.isfile(path):
        print('  appendix-b.html not found', file=sys.stderr)
        return
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()
    new_html, n = transform_html(html)
    if n == 0:
        print('  THE SENTENCE <pre><code> block not found (or already done)', file=sys.stderr)
        return
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(' done (sentence breakdown transformed)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
