#!/usr/bin/env python3
"""
Web-only: turn Appendix N's costume paragraphs into a 4-section diagnostic
card. Each costume in the source has four labeled paragraphs:

  <p><strong>Christian appearance:</strong> ...</p>
  <p><strong>Platonic substrate:</strong> ...</p>
  <p><strong>Damage:</strong> ...</p>
  <p><strong>Framework correction:</strong> ...</p>

This transform tags each paragraph with a kind-specific class so CSS can
render them as a stacked card with a colored left rail per field. Chips
that may have been injected between paragraphs survive untouched.

PDF/EPUB keep the original paragraphs.
"""
import os
import re
import sys


# Map the strong-label text (lowercased, trimmed) to a class suffix.
KIND_BY_LABEL = {
    'christian appearance': 'appearance',
    'platonic substrate':   'substrate',
    'damage':               'damage',
    'framework correction': 'correction',
}


def transform(chapters_dir):
    path = os.path.join(chapters_dir, 'appendix-n.html')
    if not os.path.isfile(path):
        print('  appendix-n.html not found', file=sys.stderr)
        return
    with open(path, 'r', encoding='utf-8') as f:
        html = f.read()

    if 'costume-field' in html:
        print(' done (costume cards already transformed)')
        return

    # Match each labeled paragraph and rewrite the opening <p> tag with the
    # appropriate kind class. Keep the inner content untouched (including any
    # nested formatting and following chips, which are siblings of <p>).
    pattern = re.compile(
        r'<p>\s*<strong>([^<:]+):</strong>',
        re.IGNORECASE,
    )

    count = [0]
    def repl(m):
        label = m.group(1).strip().lower()
        kind = KIND_BY_LABEL.get(label)
        if not kind:
            return m.group(0)
        count[0] += 1
        return (
            f'<p class="costume-field costume-field-{kind}">'
            f'<span class="costume-field-label">{m.group(1).strip()}</span> '
        )

    new_html = pattern.sub(repl, html)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_html)
    print(f' done ({count[0]} costume fields tagged)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
