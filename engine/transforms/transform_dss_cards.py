#!/usr/bin/env python3
"""
Web-only: wrap each Dead Sea Scrolls blockquote in a styled .dss-card so the
pre-Christian witness visually registers as ancient-witness instead of sitting
in the same blockquote register as Scripture and modern commentary.

Auto-detection: a plain <blockquote> (no class, or class doesn't contain
"pullquote") whose body matches a DSS citation pattern -- 1QHodayot, 1QH, 1QS,
4Q*, Community Rule, Thanksgiving Hymns/Psalms, Damascus Document, CD-A, or
a known DSS translator (Wise/Abegg/Cook, Vermes, Garcia Martinez).

Source structure typically rendered by pandoc:

  <blockquote>
  <p><em>"quote text..."</em> -- 1QHodayot 7, translated in <em>Book</em>, Authors, p. 89</p>
  </blockquote>

Parsed into:

  <div class="dss-card">
    <div class="dss-card-header">
      <span class="dss-card-badge">Dead Sea Scrolls</span>
      <span class="dss-card-source">1QHodayot 7</span>
    </div>
    <div class="dss-card-body">
      <div class="dss-card-quote">
        <p><em>"quote text..."</em></p>
      </div>
    </div>
    <div class="dss-card-attribution">translated in <em>Book</em>, Authors, p. 89</div>
  </div>

PDF/EPUB pipelines do NOT run this transform; their blockquotes stay clean.
Re-running is idempotent: the regex only matches <blockquote>, so once a
quote is wrapped in <div class="dss-card"> it is invisible to a second pass.
"""
import os
import re
import sys


# Plain blockquote (no class, or any class string that does not contain
# "pullquote"). Non-greedy body capture.
BQ_RE = re.compile(
    r'<blockquote(?P<attrs>(?:\s+[^>]*)?)>(?P<body>.*?)</blockquote>',
    re.DOTALL
)

# Citations that mark a blockquote as a DSS quote. Case-insensitive.
DSS_CITATION_RE = re.compile(
    r'1QHodayot|1QH\s+\d|1QS\s+\d|Community Rule|Thanksgiving\s+(?:Hymns|Psalms)'
    r'|4Q[A-Za-z0-9]+|Damascus Document|CD-A',
    re.IGNORECASE
)

# Trailing-attribution patterns. We only consider attribution material that
# appears AFTER the closing </em> of the italicized quote -- this prevents
# in-quote em-dashes (legitimate punctuation) from being mistaken for
# attribution boundaries. The two real-world patterns we see:
#   1. parens: ... </em> (1QHodayot 7, translated in <em>Book</em>, ...)
#   2. em-dash: ... </em> -- 1QHodayot 7, translated in <em>Book</em>, ...
# Pandoc smartypants converts `--` to `—` (real emdash), so we match the
# rendered form first plus a fallback for the literal.
PAREN_ATTR_RE = re.compile(
    r'(?P<keep></em>)\s*\((?P<attr>[^()]+)\)\s*$',
    re.DOTALL
)
EMDASH_ATTR_RE = re.compile(
    r'(?P<keep></em>)\s*(?:—|&mdash;|--)\s*(?P<attr>.+?)\s*$',
    re.DOTALL
)

# Reference extractors: try to pull a concise source label like "1QHodayot 7"
# or "1QS 3.15-17" out of the attribution. First match wins, ordered most
# specific to most general.
REF_PATTERNS = [
    re.compile(r'(1QHodayot\s+[A-Z0-9.\-]+)'),
    re.compile(r'(1QH\s+\d+(?:\.\d+(?:-\d+)?)?)'),
    re.compile(r'(1QS\s+\d+(?:\.\d+(?:-\d+)?)?)'),
    re.compile(r'(4Q[A-Za-z]+(?:\s+(?:Apocalypse|Document))?\s*\(?4Q\d+\)?(?:\s+Col\.\s+[^\s,]+)?)'),
    re.compile(r'(4Q\d+(?:\s+Col\.\s+[^\s,]+)?)'),
    re.compile(r'(Community Rule)'),
    re.compile(r'(Thanksgiving\s+(?:Hymns|Psalms))'),
    re.compile(r'(Damascus Document)'),
    re.compile(r'(CD-A[^\s,]*)'),
]

# Pandoc renders `*"text"*` as `<em>"text"</em>`. The card body keeps the em
# wrapper (italic styling intact), so we just need to peel the attribution off
# the trailing portion of the paragraph.
LAST_PARA_RE = re.compile(r'<p>(.*?)</p>\s*$', re.DOTALL)


def has_dss_citation(body: str) -> bool:
    return DSS_CITATION_RE.search(body) is not None


def is_pullquote(attrs: str) -> bool:
    return 'pullquote' in (attrs or '').lower()


def split_quote_and_attribution(body: str):
    """Peel the attribution off the end of the last paragraph in a blockquote.

    Returns (quote_html, attribution_text) where quote_html is the full
    blockquote body with the attribution stripped, and attribution_text is
    the source/translator string (or '' if no recognized pattern matched).

    The attribution must appear AFTER the closing </em> of the quoted material
    -- this avoids splitting on punctuation em-dashes inside the quote body.
    """
    # Operate on the last <p>...</p> only; earlier paragraphs are pure quote.
    m = LAST_PARA_RE.search(body)
    if not m:
        return body, ''
    last_p = m.group(1)

    for pat in (PAREN_ATTR_RE, EMDASH_ATTR_RE):
        m_attr = pat.search(last_p)
        if not m_attr:
            continue
        attr_part = m_attr.group('attr').strip()
        # If the suffix doesn't actually contain a DSS marker, it isn't
        # attribution -- skip and try the next pattern (or fall through).
        if not DSS_CITATION_RE.search(attr_part):
            continue
        # Truncate the last paragraph at the end of the closing </em>; the
        # rest of the paragraph becomes the attribution.
        cut_at = m_attr.start() + len(m_attr.group('keep'))
        quote_part = last_p[:cut_at].rstrip()
        if quote_part:
            new_last_p = f'<p>{quote_part}</p>'
            new_body = body[:m.start()] + new_last_p + body[m.end():]
        else:
            new_body = body[:m.start()] + body[m.end():]
        return new_body.rstrip(), attr_part

    return body, ''


def extract_source_label(attribution: str) -> str:
    """Pull a concise reference label (1QHodayot 7, 1QS 3.15-17, ...) out of
    the attribution. Returns '' if no recognized pattern matches."""
    for pat in REF_PATTERNS:
        m = pat.search(attribution)
        if m:
            return m.group(1).strip()
    return ''


def build_card(quote_html: str, attribution: str) -> str:
    source = extract_source_label(attribution)
    header_source = f'<span class="dss-card-source">{source}</span>' if source else ''
    attr_html = f'<div class="dss-card-attribution">{attribution}</div>' if attribution else ''
    return (
        '<div class="dss-card">\n'
        '  <div class="dss-card-header">\n'
        '    <span class="dss-card-badge">Dead Sea Scrolls</span>\n'
        f'    {header_source}\n'
        '  </div>\n'
        '  <div class="dss-card-body">\n'
        f'    <div class="dss-card-quote">{quote_html}</div>\n'
        '  </div>\n'
        f'  {attr_html}\n'
        '</div>'
    )


def transform(html: str) -> tuple[str, int]:
    count = 0

    def replace(m):
        nonlocal count
        attrs = m.group('attrs') or ''
        body = m.group('body')
        if is_pullquote(attrs):
            return m.group(0)
        if not has_dss_citation(body):
            return m.group(0)
        quote_html, attribution = split_quote_and_attribution(body)
        # Strip surrounding whitespace from quote_html for tidier output.
        quote_html = quote_html.strip()
        card = build_card(quote_html, attribution)
        count += 1
        return card

    new_html = BQ_RE.sub(replace, html)
    return new_html, count


def inject(chapters_dir: str):
    total = 0
    touched = 0
    for name in sorted(os.listdir(chapters_dir)):
        if not name.endswith('.html'):
            continue
        path = os.path.join(chapters_dir, name)
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        new_html, n = transform(html)
        if n > 0 and new_html != html:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_html)
            total += n
            touched += 1
    print(f' done ({total} DSS card{"s" if total != 1 else ""} across {touched} chapter{"s" if touched != 1 else ""})')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    inject(chapters_dir)
