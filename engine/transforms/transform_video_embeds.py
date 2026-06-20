#!/usr/bin/env python3
"""
Inject YouTube video embeds into specific chapter HTML files (web only).
The PDF/EPUB versions don't get these -- they stay clean.

Each entry: (filename, marker_text_substring, youtube_id)
"""
import os
import re
import sys

EMBEDS = [
    # Chapter 30: video removed 2026-04-23 -- the "Enough for Me" song chip
    # injected by transform_song_links.py covers the same purpose cleanly.
    # Leaving the infrastructure in place for future embeds.
]


def build_embed(yt_id):
    return (
        '<div class="chapter-video-embed">'
        '<iframe src="https://www.youtube-nocookie.com/embed/' + yt_id + '" '
        'title="YouTube video" '
        'frameborder="0" '
        'allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" '
        'referrerpolicy="strict-origin-when-cross-origin" '
        'allowfullscreen></iframe>'
        '</div>'
    )


def inject(chapters_dir):
    count = 0
    for filename, marker, yt_id in EMBEDS:
        path = os.path.join(chapters_dir, filename)
        if not os.path.isfile(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        if marker not in html:
            print(f"  marker not found in {filename}: {marker!r}", file=sys.stderr)
            continue
        if f'youtube-nocookie.com/embed/{yt_id}' in html:
            continue  # already embedded
        # Find the paragraph containing the marker and append the embed after it
        pattern = re.compile(r'(<p[^>]*>[^<]*' + re.escape(marker) + r'[^<]*</p>)', re.DOTALL)
        new_html, n = pattern.subn(lambda m: m.group(1) + '\n' + build_embed(yt_id), html, count=1)
        if n == 0:
            # Fallback: insert right after the marker string itself, at end of its paragraph
            idx = html.find(marker)
            close_p = html.find('</p>', idx)
            if close_p == -1:
                print(f"  couldn't find closing </p> after marker in {filename}", file=sys.stderr)
                continue
            new_html = html[:close_p + 4] + '\n' + build_embed(yt_id) + html[close_p + 4:]
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_html)
        count += 1
    print(f" done ({count} video embed{'s' if count != 1 else ''} injected)")


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    inject(chapters_dir)
