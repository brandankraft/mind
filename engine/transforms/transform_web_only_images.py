#!/usr/bin/env python3
"""
Inject web-only images into specific chapter HTML files.
The PDF/EPUB/Ingram versions don't get these -- they stay clean.

Each entry: (filename, marker_text_substring, image_filename, alt, caption, alignment)
- alignment is "right" or "center"
- The image must be present in the build's images directory
- The image is inserted right before the paragraph containing the marker
  so the figure floats and the paragraph text wraps around it
"""
import os
import re
import sys

IMAGES = [
    # Ch 19: Darth Vader image floats next to the Darth Gill paragraph (web only,
    # not in PDF/EPUB/Ingram for IP-risk reasons).
    (
        'chapter-19.html',
        'Darth Gill',
        'darth.jpg',
        'Darth Vader',
        'I find your lack of faith disturbing.',
        'right',
    ),
]


def build_figure(image_filename, alt, caption, alignment):
    cls = f'book-figure-{alignment}'
    return (
        f'<figure class="{cls}">'
        f'<img src="/book-content/images/{image_filename}" alt="{alt}" />'
        f'<figcaption>{caption}</figcaption>'
        f'</figure>'
    )


def inject(chapters_dir):
    count = 0
    for filename, marker, image_filename, alt, caption, alignment in IMAGES:
        path = os.path.join(chapters_dir, filename)
        if not os.path.isfile(path):
            print(f"  chapter not found: {filename}", file=sys.stderr)
            continue
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        if marker not in html:
            print(f"  marker not found in {filename}: {marker!r}", file=sys.stderr)
            continue
        if image_filename in html:
            continue  # already injected
        figure = build_figure(image_filename, alt, caption, alignment)
        # Insert the figure right before the <p> that contains the marker.
        # Float right + paragraph text wraps around it.
        idx = html.find(marker)
        # Walk backward to find the opening <p
        p_open = html.rfind('<p', 0, idx)
        if p_open == -1:
            print(f"  couldn't find opening <p before marker in {filename}", file=sys.stderr)
            continue
        new_html = html[:p_open] + figure + '\n' + html[p_open:]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_html)
        count += 1
    print(f" done ({count} web-only image{'s' if count != 1 else ''} injected)")


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    inject(chapters_dir)
