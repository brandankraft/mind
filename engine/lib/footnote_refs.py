"""Manual asterisk-footnote cross-references.

Brandan marks a handful of endnotes with a literal asterisk: an inline marker
(`sacrament\\*` -> rendered `sacrament*`) and, far later in the same appendix, a
note paragraph that begins with `\\* **On the word ...**` (rendered `<p>* ...`).
Because the note sits 15-20 pages after the marker, a print reader has no idea
where to flip.

This transform pairs each marker to its note WITHIN a single <h1> section and
rewrites both into anchored links:

    marker -> {word}<sup class="pgfn-ref"><a id="pgfn-mark-{k}-{i}"
                       href="#pgfn-{k}">*</a></sup>
    note   -> <p id="pgfn-{k}"><a class="pgfn-back"
                       href="#pgfn-mark-{k}-1">*</a> ...

The PDF stylesheet (build-book-pdf.py) turns these into live page pointers via
`target-counter` -- "(see p. N)" after the marker, "(referenced p. N)" after the
note asterisk. Web and EPUB carry no such CSS, so the same anchors render as a
plain clickable jump (marker -> note and back).

A section is only touched when it actually contains a `<p>* ...` note, so the
table footnote in Appendix I (whose note is `<p><em>*The framework...`, not a
leading bare asterisk) is left completely alone.
"""

import re

# A note definition: a paragraph whose visible text opens with a bare asterisk
# then whitespace ("<p>* <strong>..."). The bare asterisk distinguishes Brandan's
# escaped endnotes from emphasis (which pandoc has already turned into tags).
_NOTE_RE = re.compile(r'(<p\b[^>]*>)\s*\*\s')

# A marker: a letter immediately followed by a lone asterisk ("sacrament*").
# Post-pandoc, all real emphasis is tags, so a letter+asterisk in text is ours.
_MARKER_RE = re.compile(r'([A-Za-z])\*(?!\*)')

# <h1 ...> opens each chapter/appendix; markers never cross a section.
_H1_RE = re.compile(r'<h1\b')


def _section_bounds(html):
    starts = [m.start() for m in _H1_RE.finditer(html)]
    if not starts:
        return [(0, len(html))]
    bounds = []
    if starts[0] > 0:
        bounds.append((0, starts[0]))
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(html)
        bounds.append((s, e))
    return bounds


def _process_section(seg, key):
    """Rewrite markers + note in one section. Returns (new_seg, marker_count)."""
    if not _NOTE_RE.search(seg):
        return seg, 0

    nid = f"pgfn-{key}"
    idx = [0]

    def mrepl(m):
        idx[0] += 1
        i = idx[0]
        # The <a> sits at baseline (so the PDF "(see p. N)" pointer it carries via
        # ::after renders at baseline); only the asterisk glyph is raised.
        return (f'{m.group(1)}<a class="pgfn-ref" id="pgfn-mark-{key}-{i}" '
                f'href="#{nid}"><sup>*</sup></a>')

    seg2 = _MARKER_RE.sub(mrepl, seg)
    nmark = idx[0]
    if nmark == 0:
        return seg, 0

    def nrepl(m):
        ptag = m.group(1)
        if 'id=' not in ptag:
            ptag = ptag[:-1] + f' id="{nid}">'
        back = f'<a class="pgfn-back" href="#pgfn-mark-{key}-1">*</a> '
        return ptag + back

    seg3 = _NOTE_RE.sub(nrepl, seg2, count=1)
    return seg3, nmark


def transform_html(html):
    """Returns (html, marker_count). Safe to run on a single chapter or the whole
    combined book; pairing is always scoped to one <h1> section."""
    out = []
    count = 0
    key = 0
    for s, e in _section_bounds(html):
        new_seg, c = _process_section(html[s:e], key)
        if c:
            count += c
            key += 1
        out.append(new_seg)
    return ''.join(out), count


# epub_enhance.py works on whole-file strings; give it the same entry point.
def transform(html):
    return transform_html(html)


if __name__ == '__main__':
    # CLI: process every *.html in a directory in place (web post-build step).
    import sys, os, glob
    target = sys.argv[1]
    files = ([target] if os.path.isfile(target)
             else glob.glob(os.path.join(target, '*.html')))
    total = 0
    for path in files:
        with open(path, encoding='utf-8') as f:
            html = f.read()
        new_html, n = transform_html(html)
        if n:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_html)
            total += n
    print(f"  footnote_refs: {total} marker(s) linked")
