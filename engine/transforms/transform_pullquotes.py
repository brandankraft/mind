#!/usr/bin/env python3
"""
Web-only: tag short blockquotes as pull-quotes so CSS can render them as
display-style emphatic statements (large italic with accent rule) instead of
plain block quotations. Long blockquotes (extended source quotations like
Republic / Paradise Lost passages) keep regular blockquote styling.

Heuristic: a <blockquote> qualifies as a pull-quote when its plain-text
content is under MAX_LEN characters. Everything longer is left alone.
"""
import os
import re
import sys
import glob


MAX_LEN = 240  # plain-text chars; THE SENTENCE in ch1 is ~170 chars and qualifies.

BLOCKQUOTE_RE = re.compile(r'<blockquote\b([^>]*)>(.*?)</blockquote>', re.DOTALL | re.IGNORECASE)


def plain_text(html):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', html)).strip()


def add_class(attrs, cls):
    # If the attrs string already has a class= attribute, append cls; else add it.
    m = re.search(r'class\s*=\s*"([^"]*)"', attrs, flags=re.IGNORECASE)
    if m:
        if cls in m.group(1).split():
            return attrs
        return attrs[:m.start(1)] + (m.group(1) + ' ' + cls).strip() + attrs[m.end(1):]
    return f' class="{cls}"' + attrs


def transform_one(html):
    count = [0]
    def repl(m):
        attrs, inner = m.group(1), m.group(2)
        # Skip if already classified.
        if 'pullquote' in (attrs or ''):
            return m.group(0)
        text = plain_text(inner)
        if not text or len(text) > MAX_LEN:
            return m.group(0)
        count[0] += 1
        new_attrs = add_class(attrs, 'pullquote')
        return f'<blockquote{new_attrs}>{inner}</blockquote>'
    new_html = BLOCKQUOTE_RE.sub(repl, html)
    return new_html, count[0]


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
    print(f' done ({total} pull-quotes tagged across {files} files)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
