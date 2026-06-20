#!/usr/bin/env python3
"""
Web-only: convert "For Further Study" / "For further study:" paragraphs into
chip-grid cards. Two contexts handled:

1) End-of-chapter "For Further Study" section (under <h2 id="for-further-study">):
   each <p><strong>Topic:</strong> Verse 1; Verse 2; ...</p> becomes a study-card
   with the topic as header and the verses as a flex-wrap grid of small chips.

2) End-of-section inline reference lists (anywhere in any chapter):
   <p><strong>For further study:</strong> Verse 1; Verse 2; ...</p>
   becomes the same study-card layout (with the literal "For further study"
   as header).

PDF/EPUB keep the original paragraphs.
"""
import os
import re
import sys
import glob


# Match a <p> whose first child is a <strong>...:</strong> label.
# Captures: (1) label text without the trailing colon, (2) post-strong content.
TOPIC_PARA_RE = re.compile(
    r'<p>\s*<strong>([^<]+):\s*</strong>\s*(.*?)</p>',
    re.DOTALL,
)

# Verse-shaped fragment, used for both detection (heuristic) and chip splitting.
# Matches things like "Gen. 1:1", "1 Cor. 12:3-5", "John 3:16", "Rom 8:33-34".
VERSE_TOKEN_RE = re.compile(
    r'\b(?:[1-3]\s+)?[A-Z][a-z]+\.?\s+\d+:\d+(?:[–-]\d+(?::\d+)?)?'
)

# What ends the "for-further-study" section: next h2 or the next <hr>.
SECTION_END_RE = re.compile(r'<h[12]\b|<hr\s*/?>', re.IGNORECASE)


def looks_like_verse_list(content_html):
    """True when the post-strong content is mostly a semicolon-separated
    list of verse refs (3+ matches and at least one semicolon)."""
    plain = re.sub(r'<[^>]+>', '', content_html)
    if plain.count(';') < 1:
        return False
    return len(VERSE_TOKEN_RE.findall(plain)) >= 3


def split_verses(content_html):
    """Split the semicolon-delimited verse list into chip strings.
    Drops a trailing period and trims whitespace per chip.
    """
    plain = re.sub(r'<[^>]+>', '', content_html).strip()
    plain = plain.rstrip('.')
    chips = [c.strip() for c in plain.split(';')]
    return [c for c in chips if c]


def html_escape(s):
    return (
        s.replace('&', '&amp;')
         .replace('<', '&lt;')
         .replace('>', '&gt;')
         .replace('"', '&quot;')
    )


def render_card(topic, verses):
    chips_html = ''.join(
        f'<span class="study-verse">{html_escape(v)}</span>'
        for v in verses
    )
    return (
        '<div class="study-card">\n'
        f'  <h3 class="study-card-topic">{html_escape(topic.strip())}</h3>\n'
        f'  <div class="study-card-verses">{chips_html}</div>\n'
        '</div>\n'
    )


def transform_one(html):
    if 'study-card' in html:
        return html, 0

    # Locate the "for-further-study" section (chapters use <h2>, appendices may use <h3>).
    section_ranges = []
    # Prefix match the id: in the combined PDF doc pandoc de-dupes repeated
    # "for-further-study" ids to for-further-study-1, -2, ... -- the exact-match
    # form caught only chapter 1, leaving every other chapter's FFS uncarded.
    # Per-file web/EPUB ids have no suffix, so the prefix form matches them too.
    for hm in re.finditer(r'<h[123] id="for-further-study[^"]*"[^>]*>[^<]*</h[123]>', html):
        end_match = SECTION_END_RE.search(html, hm.end())
        section_end = end_match.start() if end_match else len(html)
        section_ranges.append((hm.end(), section_end))

    def in_section(pos):
        return any(s <= pos < e for s, e in section_ranges)

    # Walk all <p><strong>...:</strong>...</p> paragraphs and decide which to convert.
    matches = list(TOPIC_PARA_RE.finditer(html))
    if not matches:
        return html, 0

    out = []
    cursor = 0
    count = 0
    for m in matches:
        topic = m.group(1).strip()
        content = m.group(2).strip()

        # Eligibility:
        #   - in a "for-further-study" section, OR
        #   - the strong label is literally "For further study"
        # AND the post-strong content looks like a verse list.
        eligible = (
            in_section(m.start())
            or topic.lower() == 'for further study'
        ) and looks_like_verse_list(content)
        if not eligible:
            continue

        verses = split_verses(content)
        if not verses:
            continue

        out.append(html[cursor:m.start()])
        out.append(render_card(topic, verses))
        cursor = m.end()
        count += 1

    if count == 0:
        return html, 0

    out.append(html[cursor:])
    return ''.join(out), count


def transform(chapters_dir):
    total_files = 0
    total_cards = 0
    for path in sorted(glob.glob(os.path.join(chapters_dir, '*.html'))):
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        new_html, n = transform_one(html)
        if n > 0:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_html)
            total_files += 1
            total_cards += n
    print(f' done ({total_cards} study cards across {total_files} files)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
