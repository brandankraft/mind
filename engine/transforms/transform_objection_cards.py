#!/usr/bin/env python3
"""
Web-only: wrap each objection-and-answer pair in the "Objections and Answers"
section of every chapter as a styled card. The objection paragraph is a
quote-card header; the following paragraphs (until the next objection or
section break) are the body of the same card.

Source structure in every chapter:

  <h2 id="objections-and-answers">Objections and Answers</h2>
  <p><strong>"objection text"</strong></p>
  <p>answer paragraph 1</p>
  <p>answer paragraph 2</p>
  <p><strong>"next objection"</strong></p>
  ...
  <hr />   (or next <h2>)

PDF/EPUB keep the original paragraphs.
"""
import os
import re
import sys
import glob


# Paragraph that contains ONLY a single <strong>...</strong>: that's an
# objection header. Group 1 captures any leading index-anchor spans
# (<span class="ix-anchor"></span>) that index_anchors injects ahead of the
# strong -- they must be preserved or the topical-index deep links break.
# Group 2 captures the objection text inside the strong; it MAY contain nested
# inline markup (e.g. a footnote ref <a>), so we use (.+?) rather than [^<]+?.
# The trailing </strong>\s*</p> anchor still guarantees the paragraph is a
# strong-only paragraph (a bold LABEL followed by prose won't match because the
# strong isn't the whole paragraph), and is_quote_objection() rejects anything
# not wrapped in quote marks -- so loosening the inner class stays safe.
# Group 2 uses (?:(?!</p>).)+? -- lazy, but it must NOT cross a </p>, so a match
# can never span beyond the paragraph it starts in. Without that guard, a bold
# LABEL paragraph (<p><strong>Label:</strong> prose</p>) -- whose </strong> is
# followed by prose, not </p> -- would let .+? run forward across paragraphs to
# the next strong-only </strong></p>, swallowing every objection in between.
OBJECTION_RE = re.compile(
    r'<p>\s*((?:<span\b[^>]*></span>\s*)*)<strong>((?:(?!</p>).)+?)</strong>\s*</p>',
    re.DOTALL,
)

# A "stop" element that ends the Objections section.
SECTION_END_RE = re.compile(r'<h2\b|<hr\s*/?>', re.IGNORECASE)

# The "Objections and Answers" section heading. Objection cards are ONLY wrapped
# WITHIN such a section -- otherwise the quoted-bold heuristic mislabels pastoral
# Q&A prompts (e.g. appendix A11 "On Grief": "She's gone.") as objections.
# Match h2 OR h3 whose id starts with "objections-and-answers". Covers the
# variants across files: appendix-h (h2, bare id), appendix-a6 (h3, bare id),
# appendix-e (h2, id with a "-regeneration-..." suffix and a subtitle).
# Match the Objections section. Web/PDF (flat html5) carry the id on the h2/h3;
# pandoc's epub moves it onto a <section> wrapper -- match either.
OBJECTIONS_SECTION_RE = re.compile(
    r'<(?:h[23]|section)\b[^>]*id="objections-and-answers[^"]*"[^>]*>',
    re.IGNORECASE,
)
# The next heading (h1/h2/h3) -- or a </section> close in epub's sectioned
# markup -- that closes an Objections section.
NEXT_HEADING_RE = re.compile(r'<h[123]\b|</section>', re.IGNORECASE)


def objections_section_ranges(html):
    """Return [(start, end), ...] character ranges covering each 'Objections and
    Answers' section body (from just after its h2 heading to the next h1/h2)."""
    ranges = []
    for m in OBJECTIONS_SECTION_RE.finditer(html):
        start = m.end()
        nxt = NEXT_HEADING_RE.search(html, start)
        end = nxt.start() if nxt else len(html)
        ranges.append((start, end))
    return ranges


def is_quote_objection(strong_inner_html):
    """Heuristic: a strong-only paragraph is an objection if its inner content
    starts and ends with curly or straight double quotes -- the source's
    convention for objection-style challenger quotes. Excludes bold labels
    like 'For further study:' or section anchors.
    """
    s = strong_inner_html.strip()
    if not s:
        return False
    # Must start and end with a quote mark (ASCII or curly).
    return s[0] in '"“”' and s[-1] in '"“”.?!—'


def transform_one(html):
    """Return (new_html, count_pairs_wrapped) for a single chapter file.
    Wraps any <p><strong>"..."</strong></p> + following answer paragraphs
    into an objection card. The body of each card runs until the next
    objection-quote paragraph OR the next structural break (<h1>, <h2>,
    <h3>, <hr>, <aside>).
    """
    if 'objection-card' in html:
        return html, 0

    # Gate: only process files that actually contain an "Objections and Answers"
    # section. Inside such a file, quoted-bold paragraphs are genuine objections
    # (including ones in a topic sub-section, e.g. chapter 24 "Head Coverings").
    # Files WITHOUT an objections section (pastoral appendix A11 "On Grief", the
    # scripture index, etc.) are skipped wholesale so the quoted-bold heuristic
    # never mislabels a lament ("She's gone.") as an objection.
    if not objections_section_ranges(html):
        return html, 0

    # Find every quoted-objection paragraph anywhere in the (gated) file.
    candidates = []
    for m in OBJECTION_RE.finditer(html):
        if is_quote_objection(m.group(2)):
            candidates.append(m)
    if not candidates:
        return html, 0

    # Boundary markers. Includes <section/</section> so an objection body never
    # swallows epub's section wrappers (which would break XHTML nesting).
    BOUNDARY_RE = re.compile(
        r'<h[1-3]\b|<hr\s*/?>|<aside\b|</?section\b',
        re.IGNORECASE,
    )

    out = []
    cursor = 0
    for i, om in enumerate(candidates):
        out.append(html[cursor:om.start()])

        # Body runs from end of this objection paragraph until the next
        # objection candidate OR the next structural break -- whichever comes first.
        body_start = om.end()
        next_obj_start = candidates[i + 1].start() if i + 1 < len(candidates) else len(html)
        boundary_match = BOUNDARY_RE.search(html, body_start)
        boundary_pos = boundary_match.start() if boundary_match else len(html)
        body_end = min(next_obj_start, boundary_pos)
        body_html = html[body_start:body_end].strip()

        # Skip if the body is empty (no answer paragraphs follow) -- treat as a
        # standalone bold quote rather than a Q&A pair.
        if not body_html:
            out.append(html[om.start():om.end()])
            cursor = om.end()
            continue

        objection_text = om.group(2).strip()
        # Leading index-anchor spans (group 1) sit ahead of the strong in the
        # source paragraph; re-emit them at the card's top so topical-index deep
        # links keep resolving to this spot (same page) instead of vanishing.
        anchors = om.group(1).strip()
        # A genuine question (text ends with '?') gets the "Question" label/badge
        # instead of "Objection". Most entries are objections; only a few ask.
        inner = objection_text.strip().strip('"“”').strip()
        is_question = inner.endswith('?')
        label = 'Question' if is_question else 'Objection'
        aside_cls = 'objection-card objection-card-question' if is_question else 'objection-card'
        badge_cls = 'objection-card-badge objection-card-badge-question' if is_question else 'objection-card-badge'
        anchor_line = f'{anchors}\n' if anchors else ''
        card = (
            f'<aside class="{aside_cls}">\n'
            f'{anchor_line}'
            '  <header class="objection-card-header">\n'
            f'    <span class="{badge_cls}">{label}</span>\n'
            f'    <p class="objection-card-quote">{objection_text}</p>\n'
            '  </header>\n'
            '  <div class="objection-card-body">\n'
            f'{body_html}\n'
            '  </div>\n'
            '</aside>\n'
        )
        out.append(card)
        cursor = body_end

    out.append(html[cursor:])
    return ''.join(out), len(candidates)


def transform(chapters_dir):
    total_files = 0
    total_pairs = 0
    # Process every chapter AND appendix file -- appendices (a6, e, h, j, p, q)
    # also have Objections and Answers sections. transform_one() safely no-ops
    # on files with no objection candidates.
    for path in sorted(glob.glob(os.path.join(chapters_dir, '*.html'))):
        with open(path, 'r', encoding='utf-8') as f:
            html = f.read()
        new_html, n = transform_one(html)
        if n > 0:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_html)
            total_files += 1
            total_pairs += n
    print(f' done ({total_pairs} objection cards wrapped across {total_files} files)')


if __name__ == '__main__':
    chapters_dir = sys.argv[1]
    transform(chapters_dir)
