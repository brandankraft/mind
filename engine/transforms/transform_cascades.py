#!/usr/bin/env python3
"""
Post-processor that detects "cognition cascade" paragraphs in chapter HTML
files and rewrites them as styled loop markup.

A cognition cascade is any paragraph whose plain text contains 3 or more
" -> " separators. The chain is rendered as a vertical list of stepped nodes,
with the first and last nodes flagged as "divine" (since both refer to God's
thought) so the CSS can highlight them and visually close the loop with an
arrow connecting the last step back up to the first.

Conservative detection: a paragraph must contain at least 3 arrow separators
to be considered a cascade. This avoids false positives on prose that happens
to use a single arrow.

Idempotent: if the paragraph has already been transformed (it's no longer a
<p> with arrows in its text), it's left alone.

Runs as a build step from scripts/build-book.sh.
"""
import os
import re
import sys
import html


# Match a <p>...</p> whose decoded text contains 3+ " -> " separators.
# Use non-greedy match and DOTALL so multi-line paragraphs are handled.
PARA_PATTERN = re.compile(r'<p>(.*?)</p>', re.DOTALL)


def looks_like_cascade(inner_html):
    """Return True if this paragraph's text content has 3+ arrow separators."""
    # Decode entities and strip tags to get plain text
    text = re.sub(r'<[^>]+>', '', inner_html)
    text = html.unescape(text)
    # Normalize whitespace (paragraphs are often line-wrapped from pandoc)
    text = re.sub(r'\s+', ' ', text).strip()
    # Count " -> " or "->" with optional whitespace as separators
    arrows = len(re.findall(r'\s*->\s*', text))
    return arrows >= 3


def build_cascade_html(inner_html):
    """Convert the paragraph inner HTML to cascade markup."""
    # Strip any tags (the cascade itself uses spans, no formatting needed)
    text = re.sub(r'<[^>]+>', '', inner_html)
    text = html.unescape(text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Strip trailing punctuation from the whole sentence
    text = text.rstrip('.')
    # Split on -> with optional whitespace
    steps = [s.strip() for s in re.split(r'\s*->\s*', text) if s.strip()]
    if len(steps) < 4:
        # Not enough steps to bother
        return None

    n = len(steps)
    items = []
    for idx, step in enumerate(steps):
        is_first = (idx == 0)
        is_last = (idx == n - 1)
        cls = 'cascade-step'
        if is_first or is_last:
            cls += ' cascade-step-divine'
        # Escape the step text safely
        safe_step = html.escape(step)
        items.append(
            f'    <li class="{cls}"><span class="cascade-step-text">{safe_step}</span></li>'
        )
    items_html = '\n'.join(items)

    return (
        '<ol class="cognition-cascade" aria-label="The chain from divine thought to theology and back">\n'
        f'{items_html}\n'
        '    <li class="cascade-loopback" aria-hidden="true">'
        '<span class="cascade-loopback-icon" aria-hidden="true">\u21BA</span>'
        '<span class="cascade-loopback-text">the loop closes</span>'
        '</li>\n'
        '</ol>'
    )


def transform_html(html_text):
    """Find and replace all cascade paragraphs in an HTML string. Returns (new_html, count)."""
    count = [0]

    def replacer(match):
        inner = match.group(1)
        if not looks_like_cascade(inner):
            return match.group(0)
        cascade = build_cascade_html(inner)
        if cascade is None:
            return match.group(0)
        count[0] += 1
        return cascade

    new_html = PARA_PATTERN.sub(replacer, html_text)
    return new_html, count[0]


def main():
    if len(sys.argv) < 2:
        print("Usage: transform_cascades.py <chapters_dir>", file=sys.stderr)
        sys.exit(1)

    chapters_dir = sys.argv[1]
    if not os.path.isdir(chapters_dir):
        print(f"ERROR: not a directory: {chapters_dir}", file=sys.stderr)
        sys.exit(1)

    total_files = 0
    total_transforms = 0
    for fname in sorted(os.listdir(chapters_dir)):
        if not fname.endswith('.html'):
            continue
        path = os.path.join(chapters_dir, fname)
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        new_content, count = transform_html(content)
        if count > 0:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            total_files += 1
            total_transforms += count

    print(f"  cognition cascades: {total_transforms} paragraphs transformed across {total_files} files")


if __name__ == '__main__':
    main()
