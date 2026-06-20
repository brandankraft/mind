#!/usr/bin/env python3
"""
Extract the glossary from appendix-r.html into a standalone JSON map that the
chapter reader can load via JS for inline term tooltips.

The glossary is structured as a series of paragraphs, each beginning with
<strong>Term name.</strong> followed by the definition. We pull the term out
of the strong tag, the definition out of the rest of the paragraph, and write
both to public_html/book-content/glossary.json.

Output shape:
    {
        "Active obedience": "Christ's perfect obedience to the law on behalf of His people. Distinguished from passive obedience, which refers to His suffering and death.",
        "Amillennialism": "The eschatological position that the millennium of Revelation 20 is symbolic...",
        ...
    }

Runs as a build step from scripts/build-book.sh after split_appendix_a.py.
"""
import json
import os
import re
import sys
import html as html_module


PARA_PATTERN = re.compile(
    r'<p>\s*<strong>(.*?)</strong>\s*(.*?)\s*</p>',
    re.DOTALL
)


def clean_inline(text):
    """Strip inline tags and decode entities for either term or definition."""
    text = re.sub(r'<[^>]+>', '', text)
    text = html_module.unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def main():
    if len(sys.argv) < 2:
        print("Usage: extract_glossary.py <output_dir>", file=sys.stderr)
        sys.exit(1)

    output_dir = sys.argv[1]
    glossary_path = os.path.join(output_dir, 'chapters', 'appendix-r.html')
    out_path = os.path.join(output_dir, 'glossary.json')

    if not os.path.exists(glossary_path):
        print(f"  glossary: {glossary_path} not found, skipping")
        return

    with open(glossary_path, 'r', encoding='utf-8') as f:
        html = f.read()

    glossary = {}
    for match in PARA_PATTERN.finditer(html):
        raw_term, raw_def = match.group(1), match.group(2)
        term = clean_inline(raw_term).rstrip('.').strip()
        definition = clean_inline(raw_def)
        if not term or not definition:
            continue
        # Some terms are short stubs ("See X.") — skip those, they're cross-refs not definitions
        if definition.lower().startswith('see ') and len(definition) < 60:
            continue
        # Don't allow excessively short or ambiguous terms (single common words)
        if len(term) < 3:
            continue
        # Don't allow generic English words that would match constantly. Conservative skip list.
        if term.lower() in {'the', 'and', 'god', 'christ', 'jesus', 'spirit', 'father', 'son', 'lord'}:
            continue
        glossary[term] = definition

    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(glossary, f, ensure_ascii=False, indent=2)
        f.write('\n')

    print(f"  glossary: {len(glossary)} terms extracted to {os.path.basename(out_path)}")


if __name__ == '__main__':
    main()
