#!/usr/bin/env python3
"""
Post-process the built EPUB to bring it to parity with the web/PDF: run the
web semantic + chart transforms on each content document and inject parity CSS.

Why post-process rather than change the pandoc flow: pandoc builds the epub
straight from markdown (no HTML stage), and its TOC/chapter-splitting/image
embedding all work well. We leave that untouched and enhance the OUTPUT epub.

EPUB CSS is deliberately reader-safe: block layout (no flexbox -- e-reader
support is spotty), em/% units, no fixed widths. Renders as stacked boxes,
which reflows cleanly. Far better than the raw ASCII the epub had before.

Usage: python3 epub_enhance.py path/to/book.epub
"""
import sys, os, re, zipfile, shutil, tempfile
import html.entities

_epub_engine_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_epub_engine_dir, 'indexing'))
sys.path.insert(0, os.path.join(_epub_engine_dir, 'transforms'))
sys.path.insert(0, os.path.join(_epub_engine_dir, 'lib'))
sys.path.insert(0, _epub_engine_dir)
import transform_dss_cards, transform_pullquotes
import transform_lineage_diagram, transform_sentence_breakdown
import transform_eternal_thought_diagram, transform_book_tree, transform_cascades
import transform_objection_cards, transform_study_cards
import footnote_refs
import diagram_images

EPUB_CSS = """
/* Cinzel (inscriptional caps) sets the half-title + title-page title, echoing the
   cover. Font file embedded into EPUB/media by add_title_font(). */
@font-face { font-family: 'Cinzel'; src: url("../media/Cinzel-SemiBold.ttf"); font-weight: 600; font-style: normal; }
@font-face { font-family: 'AAtmospheric'; src: url("../media/aAtmospheric.ttf"); font-weight: normal; font-style: normal; }
.title-stack { line-height: 1.05; }
.title-stack .tl-big, .title-stack .tl-small { display: block; font-family: 'AAtmospheric', 'Cinzel', Georgia, serif; font-weight: 600; letter-spacing: 0.02em; }
/* Atmospheric is a wide display face -- smaller than Cinzel was, so the title
   doesn't overflow a narrow e-reader page. */
.title-page .title-main .tl-big { font-size: 1.7em; }
.title-page .title-main .tl-small { font-size: 1.0em; opacity: 0.8; margin: 0.12em 0; }
.half-title-page .tl-big { font-size: 1.55em; }
.half-title-page .tl-small { font-size: 0.92em; opacity: 0.8; margin: 0.1em 0; }
/* pandoc auto-injects an <h1> title from --metadata title, which duplicates our
   styled title-stack on the front page. Hide it (the anchor stays for nav). */
h1#a-thought-in-the-mind-of-god { display: none; }
/* Each chapter is its own spine file, so the reader already starts it on a fresh
   page. pandoc's stylesheet ALSO forces page-break-before:always on every h1,
   which stacks a second break on top of the file break -> a blank page before
   every chapter (visible in Apple Books). Override to auto; the file split alone
   gives each chapter its own page. (.half-title-page h1 keeps its own rule.) */
h1 { page-break-before: auto; }
/* ---- parity treatments (DSS / pull-quote / charts), reader-safe ---- */
/* Base block quotations: subtle purple accent rule so long source quotes
   (Republic, extended Scripture, Paradise Lost) match the colored pull-quote
   family instead of sitting plain. pullquote rule below overrides for the
   display tier. */
blockquote { border-left: 0.18em solid #b89ce0; padding-left: 0.9em; font-style: italic; }
blockquote.pullquote { border: none; border-left: 0.18em solid #7c3aed; padding: 0.1em 0 0.1em 0.9em; margin: 1.2em 1em; font-style: italic; font-size: 1.1em; }
.dss-card { border: 1px solid #b3a98c; background: #faf8f1; padding: 0.6em 0.8em; margin: 1.2em 0; }
.dss-card-header { margin-bottom: 0.35em; }
.dss-card-badge { text-transform: uppercase; letter-spacing: 0.07em; font-size: 0.72em; font-weight: bold; color: #6b5d3e; }
.dss-card-source { font-size: 0.8em; font-style: italic; color: #6b5d3e; margin-left: 0.5em; }
.dss-card-quote { font-style: italic; }
.dss-card-attribution { font-size: 0.78em; color: #555; margin-top: 0.4em; text-align: right; font-style: italic; }
/* Objections & Answers -- full card */
.objection-card { border: 1px solid #ccc; border-left: 0.25em solid #888; background: #fafafa; padding: 0.6em 0.8em; margin: 1.1em 0; text-align: left; }
.objection-card-header { text-align: left; margin-bottom: 0; }  /* kill pandoc's header{margin-bottom:4em} */
.objection-card-badge { display: inline-block; font-size: 0.7em; text-transform: uppercase; letter-spacing: 0.08em; font-weight: bold; color: #fff; background: #888; padding: 0.1em 0.5em; border-radius: 0.25em; }
.objection-card-quote { font-weight: bold; font-style: italic; margin: 0.3em 0 0; }
.objection-card-body { margin-top: 0.3em; }
.objection-card-body p { margin: 0.5em 0; }
.objection-card-body p:first-child { margin-top: 0; }
/* For Further Study -- chip grid */
.study-card { border: 1px solid #ddd; background: #fafafa; padding: 0.5em 0.7em; margin: 0.6em 0; }
.study-card-topic { font-size: 1em; margin: 0 0 0.3em; }
.study-card-verses { line-height: 1.9; }
.study-verse { display: inline-block; border: 1px solid #ccc; border-radius: 0.3em; padding: 0.05em 0.4em; margin: 0.15em 0.15em; font-size: 0.85em; white-space: nowrap; }
/* Related Appendices -- boxed callout */
.related-appendices { border-top: 2px solid #ccc; background: #f7f7f7; padding: 0.5em 0.8em; margin-top: 1.2em; }
.related-appendices h3 { font-size: 0.85em; text-transform: uppercase; letter-spacing: 0.06em; color: #555; margin: 0 0 0.3em; border: none; padding: 0; }
/* Cognition cascade: stacked steps, arrow via ::before */
.cognition-cascade { list-style: none; padding: 0; margin: 1.3em auto; max-width: 18em; text-align: center; }
.cognition-cascade li { margin: 0; }
.cascade-step { border: 1px solid #888; padding: 0.3em 0.5em; }
.cascade-step + .cascade-step { margin-top: 1.4em; position: relative; }
.cascade-step + .cascade-step::before { content: "\\2193"; display: block; position: absolute; top: -1.25em; left: 0; right: 0; text-align: center; color: #777; }
.cascade-step-divine { border-color: #333; border-width: 2px; font-weight: bold; background: #f2f2f2; }
.cascade-loopback { margin-top: 0.9em; font-size: 0.85em; font-style: italic; color: #666; }
.cascade-loopback-icon { margin-right: 0.3em; }
/* Single-verse scripture epigraph: indented italic block, citation floated to the
   far right of the verse's last line (falls to its own right line if it won't fit). */
.scripture-center { text-align: left; text-indent: 0; font-style: italic; color: #45508f; margin: 1.3em 1.2em 1.3em 2em; }
.scripture-center .sc-ref { float: right; font-style: italic; color: #45508f; padding-left: 0.8em; }
.scripture-center::after { content: ""; display: block; clear: both; }
/* Lineage timeline */
.lineage-diagram { margin: 1.3em 0; }
.lineage-stage { border: 1px solid #999; padding: 0.5em 0.8em; margin: 0.5em 0; }
.lineage-stage-pivot { border-width: 2px; border-color: #333; background: #f5f5f5; }
.lineage-era { font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.06em; color: #777; }
.lineage-name { font-size: 1.2em; margin: 0.1em 0 0.25em; }
.lineage-points { margin: 0.2em 0 0.2em 1.1em; padding: 0; }
.lineage-points li { margin: 0.1em 0; }
.lineage-roster { text-align: center; font-style: italic; }
.lineage-foot, .lineage-refs { font-size: 0.8em; color: #666; }
.lineage-arrow { text-align: center; margin: 0.3em 0; }
.lineage-arrow::before { content: "\\2193"; display: block; font-size: 1.2em; color: #888; }
.lineage-arrow-note { font-size: 0.75em; font-style: italic; color: #777; }
/* Eternal-thought: source + frames (stacked for reflow) */
.eternal-thought-diagram { margin: 1.3em 0; text-align: center; }
.eternal-thought-source { border: 2px solid #333; background: #f5f5f5; padding: 0.5em; margin: 0 auto; }
.eternal-thought-label { font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.06em; color: #555; }
.eternal-thought-quote { font-style: italic; font-size: 1.1em; margin: 0.15em 0; }
.eternal-thought-refs { font-size: 0.8em; color: #666; }
.eternal-thought-branch::before { content: "\\2193"; display: block; font-size: 1.2em; color: #888; margin: 0.2em 0; }
.eternal-thought-frame { border: 1px solid #999; padding: 0.4em; margin: 0.4em 0; }
.eternal-thought-frame-title { margin: 0 0 0.2em; }
.eternal-thought-frame-render { font-size: 0.8em; font-style: italic; color: #555; }
.eternal-thought-frame-ref { font-size: 0.75em; color: #777; }
/* Sentence breakdown */
.sentence-breakdown { margin: 1.3em 0; }
.sentence-breakdown-header { text-align: center; margin-bottom: 0.7em; }
.sb-label { display: block; font-size: 0.72em; text-transform: uppercase; letter-spacing: 0.08em; color: #777; }
.sb-quote { font-style: italic; font-size: 1.1em; border: none; margin: 0.3em 0; }
.sb-clauses { list-style: none; padding: 0; margin: 0; }
.sb-clause { border: 1px solid #aaa; padding: 0.4em 0.6em; margin: 0.4em 0; }
.sb-clause-num { font-size: 1.4em; font-weight: bold; color: #888; margin-right: 0.4em; }
.sb-clause-text { display: inline; font-size: 1em; }
.sb-description { margin: 0.15em 0; }
.sb-refs { font-size: 0.8em; color: #666; }
.sb-refs-label { font-weight: bold; }
/* Book-tree: monospace file tree */
.book-tree { border: 1px solid #999; margin: 1.3em 0; }
.book-tree-header { background: #ececec; border-bottom: 1px solid #999; padding: 0.25em 0.5em; }
.book-tree-dot { display: inline-block; width: 0.6em; height: 0.6em; border-radius: 50%; border: 1px solid #999; margin-right: 0.15em; }
.book-tree-title { font-family: monospace; font-size: 0.85em; margin-left: 0.4em; }
.book-tree-list { list-style: none; margin: 0; padding: 0.4em 0.6em; font-family: monospace; font-size: 0.8em; }
.book-tree-row { line-height: 1.5; }
.book-tree-branch { color: #999; margin-right: 0.3em; }
.book-tree-name { font-weight: bold; }
.book-tree-comment { color: #777; font-style: italic; margin-left: 0.4em; }
/* ---- front matter: echo the print title page (reflow-safe -- no @page rules,
   no absolute positioning, no %-padding that e-readers ignore). Each block gets
   page-break-after so the title page, copyright, and dedication each sit on their
   own screen instead of stacking in one scroll. ---- */
.half-title-page { text-align: center; margin: 4em 0; page-break-after: always; }
.half-title-page h1 { font-size: 2em; text-align: center; border: none; margin: 0; page-break-before: avoid; }
.title-page { text-align: center; margin: 3em 0 2em; page-break-after: always; }
.title-main { font-size: 1em; font-weight: bold; line-height: 1.15; margin-bottom: 0.4em; }
.title-subtitle { font-size: 1.1em; font-family: 'AAtmospheric', 'Cinzel', serif; font-weight: 600; font-style: normal; letter-spacing: .04em; margin-bottom: 2em; }
.title-author { font-size: 1.15em; font-family: 'AAtmospheric', 'Cinzel', Georgia, serif; font-weight: 600; letter-spacing: 0.04em; margin-bottom: 0.4em; }
.title-publisher { font-size: 0.95em; color: #333; margin-top: 3em; }
.copyright-page { font-size: 0.85em; line-height: 1.5; margin: 2em 0; page-break-after: always; }
.dedication-page { text-align: center; font-style: italic; margin: 4em 1.5em; page-break-after: always; }
/* ---- narrow tables (<= 3 cols): real borders, fit fine on a phone ---- */
table { border-collapse: collapse; width: 100%; margin: 1.2em 0; font-size: 0.85em; }
th, td { border: 1px solid #bbb; padding: 0.3em 0.45em; text-align: left; vertical-align: top; word-wrap: break-word; overflow-wrap: break-word; }
thead th { background: #ededed; }
/* ---- responsive tables (4+ cols): DEFAULT = stacked cards (one row per card,
   each cell labeled by its column header via data-label). This is the safe
   baseline -- readers that ignore media queries (and narrow phones) get it.
   A min-width media query per column count (below) restores the real grid on
   wide viewports. ---- */
table.rt { display: block; width: auto; border: none; margin: 1.3em 0; font-size: 1em; }
table.rt thead { display: none; }
table.rt tbody { display: block; }
table.rt tr { display: block; border: 1px solid #bbb; border-left: 0.22em solid #888; background: #fafafa; padding: 0.45em 0.75em; margin: 0.7em 0; page-break-inside: avoid; }
table.rt td { display: block; border: none; padding: 0; margin: 0.12em 0; line-height: 1.45; }
table.rt td:first-child { font-weight: bold; font-size: 1.05em; margin: 0 0 0.35em; }
table.rt td[data-label]::before { content: attr(data-label) ": "; font-weight: bold; }
table.rt td:empty { display: none; }
/* Numbered endnotes: surfaced as reader popups via epub:type="noteref"/"footnote".
   Hide the inline end-of-chapter list so there's no vestigial blank "Notes" block;
   the popup reads the note content regardless of CSS display. (Readers with no
   popup support won't show these inline -- the web and PDF carry them in full.) */
.footnotes { display: none; }
a.footnote-ref, a.footnote-back { text-decoration: none; }

/* ---- Cover/web color palette (purple-forward, headings stay black) ----
   Matches the print interior and web: purple leads, gold + blue/red accents.
   Flat tints (no gradients) so it reproduces consistently across e-readers. */
blockquote.pullquote { border-left-color: #7c3aed; background: #f3effc; }
.dss-card { border-color: #c3a868; background: #f4ead2; border-radius: 10px; box-shadow: 0 1.5px 5px rgba(60,40,10,.10); }
.dss-card-header { background: transparent; }
.dss-card-badge { color: #6b4a1e; }
.dss-card-source { color: #7a5a2e; }
.dss-card-quote { color: #352809; }
.anchor-verse-callout { border-left-color: #c98a2e; background: #f7eede; }
.anchor-verse-badge { color: #b07418; }
.objection-card-badge { background: #7a5ea8; }
.cascade-step { border-color: #9aa0b4; background: #f6f5fb; }
.cascade-step + .cascade-step::before { color: #8b5cf6; }
.cascade-step-divine { border-color: #7c3aed; background: #ece5fb; color: #5b21b6; }
.lineage-stage { border-color: #b9b9c6; }
.lineage-stage-pivot { border-color: #d4a24a; background: #f8efdc; }
.lineage-stage-pivot .lineage-era { color: #b07418; }
.eternal-thought-source { border-color: #d4a24a; background: #f8efdc; }
.eternal-thought-label { color: #b07418; }
.sb-clause-num { color: #b07418; }
/* Header: DARK text on a light lavender wash + purple underline. (White-on-purple
   breaks in readers that strip cell backgrounds in light mode -> white-on-white.)
   Dark text stays legible whether or not the reader keeps the background, and in
   dark mode the reader inverts it to light-on-dark. */
thead th { background: #ece5fb; color: #4a2d7a; font-weight: bold; border-bottom: 2px solid #6d28d9; }
tbody tr:nth-child(even) { background: #f5f1fc; }
table.rt td:first-child { color: #7c3aed; }
td em { color: #7c3aed; }
/* macOS code-editor book-tree (dark chrome + traffic-light dots) */
.book-tree { background: #1e1e2e; border-color: #1e1e2e; color: #e2e2f0; }
.book-tree-header { background: #2a2a3e; border-bottom-color: #11111a; }
.book-tree-dot-r { background: #ff5f57; border-color: #ff5f57; }
.book-tree-dot-y { background: #febc2e; border-color: #febc2e; }
.book-tree-dot-g { background: #28c840; border-color: #28c840; }
.book-tree-title { color: #cfcfe0; }
.book-tree-name { color: #a78bfa; }
.book-tree-branch { color: #6a6a85; }
.book-tree-comment { color: #6a8c6a; }
/* study cards (violet) + related appendices (blue) */
.study-card { border-color: #cdbbe6; background: #f6f2fc; }
.study-card-topic { color: #6d28d9; }
.study-verse { background: #ece5fb; border-color: #cdbbe6; }
.related-appendices { border-top-color: #aaccea; background: #eef5fb; }
.related-appendices h3 { color: #1f5f8b; }
/* colored horizontal rules + chapter-title underline */
hr { border: none; height: 2px; background: linear-gradient(90deg, rgba(124,58,237,0) 0%, #7c3aed 28%, #b07418 72%, rgba(176,116,24,0) 100%); width: 50%; margin: 2em auto; }
h1 { border-bottom: 1px solid #c9b3e8; padding-bottom: 0.15em; }
.half-title-page h1 { border-bottom: none; padding-bottom: 0; }
/* figures: rounded corners, centered, small italic caption */
figure { margin: 1.2em auto; text-align: center; }
figure img, .book-figure-center img, .book-figure-pair img { max-width: 100%; height: auto; border-radius: 8px; }
/* Portrait variant (App I/J/M/N people): centered, capped narrower than full width */
.book-figure-portrait { margin: 1.2em auto; text-align: center; }
.book-figure-portrait img { max-width: 60%; height: auto; border-radius: 8px; }
/* Portrait gallery (App I "The Systems Compared"): inline-block grid (~3 across)
   instead of a vertical stack. inline-block is the reliable EPUB layout -- on
   readers that don't honor the width it degrades to a clean centered stack. */
.portrait-gallery { text-align: center; margin: 1.2em 0 1.6em; }
.portrait-gallery figure { display: inline-block; vertical-align: top; width: 30%; margin: 0.4em 1%; text-align: center; }
.portrait-gallery img { width: 100%; height: auto; border-radius: 6px; }
.portrait-gallery figcaption { font-size: 0.72em; font-style: italic; color: #555; margin-top: 0.3em; line-height: 1.25; }
/* Diagram plates (eternal-thought, cascades, lineage) rendered wide. */
.book-figure-wide { margin: 1.3em 0; text-align: center; }
.book-figure-wide img { max-width: 85%; height: auto; display: block; margin: 0 auto; border-radius: 6px; }
/* Alternating float plates (Appendix L) -- readers that ignore float just center them. */
.book-figure-float-left, .book-figure-float-right { max-width: 45%; margin: 0.3em 0 0.8em; }
.book-figure-float-left { float: left; margin-right: 1em; }
.book-figure-float-right { float: right; margin-left: 1em; }
.book-figure-float-left img, .book-figure-float-right img { max-width: 100%; height: auto; border-radius: 6px; }
figcaption { font-size: 0.82em; font-style: italic; color: #555; text-align: center; margin-top: 0.4em; line-height: 1.35; }
"""

# Per-column-count grid: a 4-col table needs less width than a 7-col one, so each
# only "un-stacks" into a real grid once the viewport is wide enough to hold it.
def _rt_grid(sel):
    return (
        f"{sel} {{ display: table; width: 100%; border-collapse: collapse; margin: 1.2em 0; border: none; }}"
        f"{sel} thead {{ display: table-header-group; }}"
        f"{sel} tbody {{ display: table-row-group; }}"
        f"{sel} tr {{ display: table-row; border: none; background: none; padding: 0; margin: 0; }}"
        f"{sel} th, {sel} td {{ display: table-cell; border: 1px solid #bbb; padding: 0.3em 0.45em; "
        f"vertical-align: top; text-align: left; font-weight: normal; font-size: 0.8em; margin: 0; line-height: 1.3; "
        f"word-wrap: break-word; overflow-wrap: break-word; }}"
        f"{sel} thead th {{ background: #ece5fb; color: #4a2d7a; font-weight: bold; border-bottom: 2px solid #6d28d9; }}"
        f"{sel} td:first-child {{ font-weight: normal; font-size: 0.8em; margin: 0; }}"
        f"{sel} td::before {{ content: none; }}"
    )

# breakpoint per column count (em scales with the reader's font size)
_RT_BREAKS = {4: "40em", 5: "47em", 6: "55em", 7: "63em"}
EPUB_CSS += "\n" + "\n".join(
    f"@media (min-width: {bp}) {{ {_rt_grid(f'table.rt-c{n}')} }}"
    for n, bp in _RT_BREAKS.items()
)


_XML_SAFE = {'amp', 'lt', 'gt', 'quot', 'apos'}


def _named_entities_to_unicode(s):
    """Convert HTML named entities (e.g. &ldquo; &mdash; &middot;) to literal
    Unicode chars. EPUB is XHTML/XML, which only defines amp/lt/gt/quot/apos --
    any other named entity is undefined and breaks the XML parser. The injected
    web partials use named entities, so we normalize them here. pandoc's own
    epub output uses Unicode literals (not named entities), so this is safe to
    run over the whole document."""
    def repl(m):
        name = m.group(1)
        if name in _XML_SAFE:
            return m.group(0)
        ch = html.entities.html5.get(name + ';') or html.entities.html5.get(name)
        return ch if ch else m.group(0)
    return re.sub(r'&([a-zA-Z][a-zA-Z0-9]*);', repl, s)


_SECTION_HEAD_RE = re.compile(
    r'<section\b([^>]*?)\sid="([^"]+)"([^>]*)>(\s*)<h([1-6])\b([^>]*?)>')


def _anchor_ids_to_headings(s):
    """Move each pandoc <section id="X"> anchor onto its first heading
    (<hN id="X">), dropping it from the section.

    Why: pandoc puts the link target id on the wrapping <section>. Its box top
    sits ABOVE the heading's top margin and BEFORE the heading's
    page-break-before, so paginating desktop readers (Apple Books, ADE) round the
    anchor onto the PREVIOUS screen-page -- every internal link lands one page
    early. Anchoring the heading element itself (which sits after the break,
    below its margin) puts the target on the correct page. Fragment links and the
    nav still resolve -- the id just moved to the heading at the same spot."""
    def repl(m):
        pre, sid, post, ws, lvl, hattrs = m.groups()
        if re.search(r'\bid=', hattrs):   # heading already has an id -- leave as-is
            return m.group(0)
        return f'<section{pre}{post}>{ws}<h{lvl}{hattrs} id="{sid}">'
    return _SECTION_HEAD_RE.sub(repl, s)


_TAG_RE = re.compile(r'<[^>]+>')
_CELL_RE = re.compile(r'<t[hd]\b[^>]*>(.*?)</t[hd]>', re.DOTALL | re.I)
_ROW_RE = re.compile(r'<tr\b[^>]*>(.*?)</tr>', re.DOTALL | re.I)
_TABLE_RE = re.compile(r'<table\b[^>]*>(.*?)</table>', re.DOTALL | re.I)
_NUM_HEADERS = {'#', 'no.', 'no', 'num', 'nr'}


def _clean_cell(html_frag):
    """Collapse the internal newlines pandoc inserts inside a cell, trim."""
    return re.sub(r'\s+', ' ', html_frag).strip()


def _plain(html_frag):
    return _clean_cell(_TAG_RE.sub('', html_frag))


def _attr_escape(text):
    return text.replace('&', '&amp;').replace('"', '&quot;')


def _make_tables_responsive(s, min_cols=4):
    """Make tables with >= min_cols columns responsive (viewport-driven): keep the
    real <table>, tag it `rt rt-cN`, and stamp every body <td> with a
    data-label="<column header>". CSS then renders it as stacked labeled cards by
    default (safe on phones + readers that ignore media queries) and snaps it back
    to a real grid once the viewport is wide enough (per-column-count breakpoint).

    Tables with <= 3 columns fit a phone, so they're left as plain tables."""
    def repl(m):
        tbl = m.group(0)
        rows = _ROW_RE.findall(m.group(1))
        if len(rows) < 2:
            return tbl
        headers = [_plain(c) for c in _CELL_RE.findall(rows[0])]
        ncols = len(headers)
        if ncols < min_cols:
            return tbl

        # Stamp data-label on every <td> in the body rows (skip the header row and
        # the first column -- that one renders as the card title).
        seen = [0]

        def row_repl(rm):
            seen[0] += 1
            if seen[0] == 1:                       # header row: leave alone
                return rm.group(0)
            cidx = [0]

            def td_repl(tdm):
                i = cidx[0]
                cidx[0] += 1
                tag = tdm.group(0)
                if i == 0 or 'data-label' in tag:
                    return tag
                lbl = _attr_escape(headers[i]) if i < len(headers) else ''
                return re.sub(r'<td\b', f'<td data-label="{lbl}"', tag, count=1)

            inner = re.sub(r'<td\b[^>]*>', td_repl, rm.group(1))
            return rm.group(0).replace(rm.group(1), inner, 1)

        tbl = _ROW_RE.sub(row_repl, tbl)

        # Tag the <table> with rt + rt-cN (merge with any existing class).
        def add_class(tm):
            tag = tm.group(0)
            if 'class="' in tag:
                return re.sub(r'class="([^"]*)"',
                              lambda c: f'class="{c.group(1)} rt rt-c{ncols}"', tag, count=1)
            return tag[:-1] + f' class="rt rt-c{ncols}">'
        return re.sub(r'<table\b[^>]*>', add_class, tbl, count=1)
    return _TABLE_RE.sub(repl, s)


def enhance_html(s):
    s, _ = transform_dss_cards.transform(s)
    s, _ = transform_pullquotes.transform_one(s)
    # pandoc's epub carries the heading id on a <section> wrapper, which the
    # objection-card gate now recognizes; its body stops at </section> so the
    # card never crosses the section boundary.
    s, _ = transform_objection_cards.transform_one(s)
    s, _ = transform_study_cards.transform_one(s)
    # For Further Study chips are emitted with NO whitespace between them, so the
    # inline-block chips have no soft-wrap opportunity and the row overflows the
    # column. Inject a space between adjacent chips so they wrap (each chip is
    # nowrap, so refs never split mid-token).
    s = s.replace('</span><span class="study-verse">',
                  '</span> <span class="study-verse">')
    s, _ = transform_lineage_diagram.transform_html(s)
    s, _ = transform_sentence_breakdown.transform_html(s)
    s, _ = transform_eternal_thought_diagram.transform_html(s)
    s, _ = transform_book_tree.transform_html(s)
    s, _ = transform_cascades.transform_html(s)
    # Standalone single-verse epigraph: indented italic block, citation floated to
    # the far right of the last line (mirrors the PDF). Split the trailing
    # parenthetical citation into its own .sc-ref span.
    s = re.sub(
        r'<p>(<em>[“"][^<]*[”"]</em>)\s*(\([^)]*\d+:\d+[^)]*\))</p>',
        r'<p class="scripture-center">\1<span class="sc-ref">\2</span></p>', s)
    # Swap the eternal-thought + god-thinks CSS diagrams for image figures
    # (e-reader edition; web keeps the CSS). Images live in EPUB/media/.
    s, _ = diagram_images.swap_print_diagrams(s, img_prefix="../media/")
    # Manual asterisk endnotes -> clickable marker/note jump (no page numbers in a
    # reflowable EPUB). See scripts/lib/footnote_refs.py.
    s, _ = footnote_refs.transform_html(s)
    # Tables with 4+ cols -> responsive: stacked cards on phones, real grid on
    # wide viewports (via per-column-count media queries in EPUB_CSS).
    s = _make_tables_responsive(s)
    # Related Appendices: pandoc already wraps it in <section id="related-appendices">.
    # Add a class to that section so CSS can box it -- no fragile wrapping.
    s = re.sub(r'(<section\b[^>]*id="related-appendices[^"]*"[^>]*class=")',
               r'\1related-appendices ', s)
    # Move section anchor ids onto their headings so internal links don't land one
    # page early on desktop readers (run AFTER the related-appendices class inject,
    # which keys off the section id).
    s = _anchor_ids_to_headings(s)
    # XHTML safety: the partials emit HTML5 <br> and named entities; epub is XML.
    s = re.sub(r'<br>', '<br/>', s)
    s = _named_entities_to_unicode(s)
    return s


def _loose(slug):
    """Period- and hyphen-run-insensitive form of an anchor slug. pandoc keeps
    '.' in ids (e.g. 'vs.', 'analog.') but the cross-ref slug generator strips
    them, so a link's fragment and the real id differ only by dropped periods (and
    sometimes collapsed hyphens). Comparing loose forms lets us re-pair them."""
    return re.sub(r'-{2,}', '-', slug.replace('.', '').lower()).strip('-')


def link_cross_file_anchors(tmp):
    """Point bare `href="#id"` links at the split file that actually contains `id`.

    pandoc's epub writer rewrites cross-file links for ids it tracks (headings), but
    NOT for the empty-span anchors the topical index stamps (`<span id="ix-...">`),
    so every index link stays bare `#ix-...` and resolves to the top of the index's
    OWN file. Here we build id -> filename from the generated xhtml and retarget any
    bare link whose id lives in a different file. ONLY the topical-index anchors
    (`ix-*`) are treated as cross-file; everything else -- crucially the per-chapter
    pandoc footnote ids (`fn1`/`fnref1`, which repeat in every split file) and the
    asterisk-footnote anchors -- stays bare and intra-file. (Retargeting footnote
    ids broke every chapter's notes to one wrong file's popup.)"""
    xhtmls = [os.path.join(r, fn) for r, _, fs in os.walk(tmp)
              for fn in fs if fn.endswith('.xhtml')]
    id_to_file = {}
    for p in xhtmls:
        base = os.path.basename(p)
        for i in re.findall(r'\sid="(ix-[^"]+)"', open(p, encoding='utf-8').read()):
            id_to_file.setdefault(i, base)   # ix-* ids are globally unique

    retargeted = 0
    for p in xhtmls:
        here = os.path.basename(p)
        s = open(p, encoding='utf-8').read()

        def fix(m):
            nonlocal retargeted
            frag = m.group(1)
            if not frag.startswith('ix-'):   # leave footnote + all non-index links alone
                return m.group(0)
            tgt = id_to_file.get(frag)
            if tgt and tgt != here:
                retargeted += 1
                return f'href="{tgt}#{frag}"'
            return m.group(0)

        ns = re.sub(r'href="#([^"]+)"', fix, s)
        if ns != s:
            open(p, 'w', encoding='utf-8').write(ns)
    if retargeted:
        print(f'  retargeted {retargeted} cross-file anchor link(s)')


def repair_internal_links(tmp):
    """Fix internal anchor links whose fragment doesn't match any heading id,
    re-pairing them by loose comparison against the real ids. Runs after all docs
    are enhanced (ids are on headings by now) so it sees the final id set across
    every file. Only rewrites when the loose form maps to exactly one real id."""
    xhtmls = [os.path.join(r, fn) for r, _, fs in os.walk(tmp)
              for fn in fs if fn.endswith('.xhtml')]
    ids = set()
    for p in xhtmls:
        ids.update(re.findall(r'\sid="([^"]+)"', open(p, encoding='utf-8').read()))
    loose_map = {}
    for i in ids:
        k = _loose(i)
        loose_map[k] = i if k not in loose_map else (loose_map[k] if loose_map[k] == i else None)
    fixed, unresolved = 0, set()

    def fix(m):
        nonlocal fixed
        path, frag = m.group(1), m.group(2)
        if frag in ids:
            return m.group(0)
        cand = loose_map.get(_loose(frag))
        if cand:
            fixed += 1
            return f'href="{path}#{cand}"'
        unresolved.add(frag)
        return m.group(0)

    for p in xhtmls:
        s = open(p, encoding='utf-8').read()
        ns = re.sub(r'href="([^"#]*)#([^"]+)"', fix, s)
        if ns != s:
            open(p, 'w', encoding='utf-8').write(ns)
    if fixed:
        print(f'  repaired {fixed} internal anchor link(s) with slug mismatches')
    if unresolved:
        print('  WARNING: internal links with no matching id (broken):', file=sys.stderr)
        for u in sorted(unresolved):
            print('    #' + u, file=sys.stderr)


def reorder_frontmatter_nav(tmp):
    """Move the auto-generated TOC (nav) in the spine to sit AFTER the front
    matter (half-title, title page, copyright, dedication) rather than before it.

    pandoc inserts the nav right after the cover -- so the reading order is
    cover -> TOC -> half-title -> title page, and the book opens onto the orphan
    half-title 'between the TOC and the title page'. Book convention is
    cover -> half-title -> title page -> copyright -> dedication -> TOC -> body.
    We relocate the nav itemref to immediately after the title-page spine item
    (the file that also carries copyright + dedication)."""
    opfs = [os.path.join(r, fn) for r, _, fs in os.walk(tmp)
            for fn in fs if fn.endswith('.opf')]
    if not opfs:
        return
    opf = opfs[0]
    s = open(opf, encoding='utf-8').read()

    # Which xhtml renders the title page?
    titlepage = None
    for r, _, fs in os.walk(tmp):
        for fn in fs:
            if fn.endswith('.xhtml') and 'class="title-page"' in open(os.path.join(r, fn), encoding='utf-8').read():
                titlepage = fn
                break
    if not titlepage:
        return
    # Manifest id for that file's href (href ends with the basename).
    mid = re.search(r'<item\b[^>]*\bid="([^"]+)"[^>]*\bhref="[^"]*' + re.escape(titlepage) + r'"', s) \
        or re.search(r'<item\b[^>]*\bhref="[^"]*' + re.escape(titlepage) + r'"[^>]*\bid="([^"]+)"', s)
    if not mid:
        return
    tp_id = mid.group(1)

    nav_re = re.compile(r'[ \t]*<itemref\b[^>]*\bidref="nav"[^>]*/>\s*\n')
    m = nav_re.search(s)
    if not m:
        return
    nav_line = m.group(0)
    s2 = s[:m.start()] + s[m.end():]            # remove nav itemref
    # reinsert right after the title-page itemref
    tp_ref = re.search(r'([ \t]*<itemref\b[^>]*\bidref="' + re.escape(tp_id) + r'"[^>]*/>\s*\n)', s2)
    if not tp_ref:
        return                                   # leave as-is rather than corrupt order
    insert_at = tp_ref.end()
    s2 = s2[:insert_at] + nav_line + s2[insert_at:]
    open(opf, 'w', encoding='utf-8').write(s2)
    print('  reordered spine: TOC now follows the front matter')


def add_print_diagram_images(tmp, src_dir):
    """Copy the swapped-in diagram PNGs into the EPUB media dir and register them
    in the OPF manifest (an unmanifested resource is invalid EPUB and some readers
    silently drop it). No-op if src_dir is missing or the images aren't present."""
    if not src_dir:
        return
    # Locate the OPF (content.opf) and derive media dir alongside it.
    opf = None
    for root, _, files in os.walk(tmp):
        for fn in files:
            if fn.endswith('.opf'):
                opf = os.path.join(root, fn)
                break
        if opf:
            break
    if not opf:
        return
    media_dir = os.path.join(os.path.dirname(opf), 'media')
    os.makedirs(media_dir, exist_ok=True)
    opf_text = open(opf, encoding='utf-8').read()
    added = []
    for fname in diagram_images.IMAGE_FILES:
        srcf = os.path.join(src_dir, fname)
        if not os.path.exists(srcf):
            continue
        shutil.copyfile(srcf, os.path.join(media_dir, fname))
        item_id = 'img_' + re.sub(r'[^a-zA-Z0-9]', '_', fname)
        if f'href="media/{fname}"' not in opf_text:
            added.append(f'    <item id="{item_id}" href="media/{fname}" media-type="image/png" />')
    if added:
        opf_text = opf_text.replace('</manifest>', '\n'.join(added) + '\n  </manifest>')
        open(opf, 'w', encoding='utf-8').write(opf_text)


def add_title_font(tmp):
    """Embed the title-page fonts into EPUB/media and register them in the OPF manifest.
    EPUB_CSS @font-faces reference ../media/Cinzel-SemiBold.ttf and ../media/aAtmospheric.ttf
    (the cover face). An unmanifested resource is invalid EPUB and some readers drop it."""
    fontdir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
    fonts = [('Cinzel-SemiBold.ttf', 'font_cinzel'), ('aAtmospheric.ttf', 'font_atmos')]
    opf = None
    for root, _, files in os.walk(tmp):
        for fn in files:
            if fn.endswith('.opf'):
                opf = os.path.join(root, fn); break
        if opf:
            break
    if not opf:
        return
    media_dir = os.path.join(os.path.dirname(opf), 'media')
    os.makedirs(media_dir, exist_ok=True)
    opf_text = open(opf, encoding='utf-8').read()
    for fname, item_id in fonts:
        src = os.path.join(fontdir, fname)
        if not os.path.exists(src):
            continue
        shutil.copyfile(src, os.path.join(media_dir, fname))
        if f'href="media/{fname}"' not in opf_text:
            item = (f'    <item id="{item_id}" href="media/{fname}" '
                    'media-type="application/vnd.ms-opentype" />')
            opf_text = opf_text.replace('</manifest>', item + '\n  </manifest>')
    open(opf, 'w', encoding='utf-8').write(opf_text)


def repair_broken_links(tmp):
    """Final safety net: resolve every internal <a> link in the content against the
    full id map. A bare or wrong `#frag` whose id lives in another file is retargeted
    to that file; a `#frag` that exists nowhere is unwrapped to plain text. This is
    what stops KDP's "broken link in your Table of Contents" rejection."""
    import collections
    texts = [os.path.join(r, f) for r, _, fs in os.walk(tmp)
             for f in fs if f.endswith('.xhtml') and f != 'nav.xhtml']
    id2file, ids = collections.defaultdict(list), {}
    for p in texts:
        fn = os.path.basename(p)
        these = set(re.findall(r'\bid="([^"]+)"', open(p, encoding='utf-8').read()))
        ids[fn] = these
        for i in these:
            id2file[i].append(fn)
    retarget = unwrap = 0
    for p in texts:
        src = os.path.basename(p)
        s = open(p, encoding='utf-8').read()

        def repl(m):
            nonlocal retarget, unwrap
            whole, href, inner = m.group(0), m.group(1), m.group(2)
            if href.startswith(('http', 'mailto', 'tel')):
                return whole
            file, _, frag = href.partition('#')
            file = os.path.basename(file) if file else src
            if (not frag) or (file in ids and frag in ids[file]):
                return whole
            holders = id2file.get(frag, [])
            if holders:
                retarget += 1
                return f'<a href="{holders[0]}#{frag}">{inner}</a>'
            unwrap += 1
            return inner

        ns = re.sub(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', repl, s, flags=re.DOTALL)
        if ns != s:
            open(p, 'w', encoding='utf-8').write(ns)
    if retarget or unwrap:
        print(f'  repaired broken links: {retarget} retargeted, {unwrap} unwrapped (KDP)')


def drop_hidden_toc_entries(tmp):
    """THE fatal-error fix (Kindle Previewer E24010 / E24001 "table of content could
    not be built"): pandoc lists the half-title h1 as the first TOC entry, but that
    heading is hidden via `h1#... { display: none }` (the visible title is drawn with
    styled spans). Kindle cannot resolve a TOC link to a display:none target and aborts
    the whole TOC build -> KDP rejects with "broken link in your Table of Contents".
    epubcheck passes this; only Kindle's converter flags it. Drop nav + NCX entries that
    point at any id hidden by display:none."""
    hidden = set()
    for css in [os.path.join(r, f) for r, _, fs in os.walk(tmp)
                for f in fs if f.endswith('.css')]:
        for m in re.finditer(r'#([A-Za-z0-9_-]+)\s*\{[^}]*display\s*:\s*none',
                             open(css, encoding='utf-8').read()):
            hidden.add(m.group(1))
    if not hidden:
        return
    for nav in [os.path.join(r, f) for r, _, fs in os.walk(tmp)
                for f in fs if f == 'nav.xhtml']:
        s = open(nav, encoding='utf-8').read(); ns = s
        for hid in hidden:
            ns = re.sub(r'<li[^>]*><a href="[^"]*#' + re.escape(hid) + r'">.*?</a></li>',
                        '', ns, flags=re.DOTALL)
        if ns != s:
            open(nav, 'w', encoding='utf-8').write(ns)
    for ncx in [os.path.join(r, f) for r, _, fs in os.walk(tmp)
                for f in fs if f.endswith('.ncx')]:
        s = open(ncx, encoding='utf-8').read(); ns = s
        for hid in hidden:
            ns = re.sub(r'\s*<navPoint[^>]*>\s*<navLabel>.*?</navLabel>\s*'
                        r'<content src="[^"]*#' + re.escape(hid) + r'"\s*/>\s*</navPoint>',
                        '', ns, flags=re.DOTALL)
        if ns != s:
            open(ncx, 'w', encoding='utf-8').write(ns)
            print('  dropped hidden (display:none) TOC entries (Kindle E24010 fix)')


def fix_nav_landmarks(tmp):
    """Kindle/KDP rejects the upload ("broken link in your Table of Contents")
    because pandoc points BOTH `toc` references -- the landmarks-nav `<a epub:type="toc"
    href="#toc">` AND the OPF `<guide>` `<reference type="toc" href="nav.xhtml">` -- at
    the nav document, which is NOT a spine (reading-order) item. KindleGen requires a
    toc reference to resolve to a spine document, so it flags both as broken. The real
    logical TOC (the <nav epub:type="toc"> list + the NCX) is what readers and KDP build
    the Kindle TOC from, so we drop both stray pointers. The cover references stay."""
    # 1. nav.xhtml: drop the `#toc` landmark <li> (keep the real <nav epub:type="toc">).
    for nav in [os.path.join(r, f) for r, _, fs in os.walk(tmp)
                for f in fs if f == 'nav.xhtml']:
        s = open(nav, encoding='utf-8').read()
        ns = re.sub(r'\s*<li>\s*<a [^>]*href="#toc"[^>]*>.*?</a>\s*</li>',
                    '', s, flags=re.DOTALL)
        if ns != s:
            open(nav, 'w', encoding='utf-8').write(ns)
            print('  fixed nav: removed broken #toc landmark (KDP TOC-link error)')
    # 2. content.opf: drop the legacy <guide> toc reference to the non-spine nav.
    for opf in [os.path.join(r, f) for r, _, fs in os.walk(tmp)
                for f in fs if f.endswith('.opf')]:
        s = open(opf, encoding='utf-8').read()
        ns = re.sub(r'\s*<reference[^>]*type="toc"[^>]*/>', '', s)
        ns = re.sub(r'\s*<guide>\s*</guide>', '', ns)  # tidy up if now empty
        if ns != s:
            open(opf, 'w', encoding='utf-8').write(ns)
            print('  fixed opf: removed broken guide toc reference (KDP TOC-link error)')


def main(epub_path, src_dir=None):
    tmp = tempfile.mkdtemp(prefix='epub_enhance_')
    with zipfile.ZipFile(epub_path) as z:
        z.extractall(tmp)

    changed = 0
    for root, _, files in os.walk(tmp):
        for fn in files:
            p = os.path.join(root, fn)
            if fn.endswith('.xhtml') and fn != 'nav.xhtml':
                s = open(p, encoding='utf-8').read()
                ns = enhance_html(s)
                if ns != s:
                    open(p, 'w', encoding='utf-8').write(ns)
                    changed += 1
                    # Guard the exact failure mode: any named entity other than
                    # the five XML-predefined ones is undefined in XHTML and
                    # renders as a parse-error page in e-readers. Scan with a
                    # regex (no XML parser -> no XXE/billion-laughs surface).
                    bad = set(re.findall(r'&([a-zA-Z][a-zA-Z0-9]*);', ns)) - _XML_SAFE
                    if bad:
                        print(f'  !! undefined named entities in {fn}: {sorted(bad)}', file=sys.stderr)
            elif fn.endswith('.css'):
                with open(p, 'a', encoding='utf-8') as f:
                    f.write('\n' + EPUB_CSS)

    # Retarget bare `#id` links (the topical index's span anchors) to the file that
    # holds the id -- pandoc leaves these cross-file links bare. Must run BEFORE
    # repair_internal_links so the now-FILE#frag links go through slug repair too.
    link_cross_file_anchors(tmp)

    # Re-pair internal anchor links whose slug doesn't match the real heading id
    # (cross-ref slugs drop periods pandoc keeps; see repair_internal_links).
    repair_internal_links(tmp)

    # Catch-all safety net AFTER the targeted passes: any remaining broken internal
    # <a> link (a bare `#frag` cross-ref like the Appendix-D heading links, or an
    # index anchor that was never stamped) is what KDP rejects as a "broken link in
    # your Table of Contents." Retarget a bare/wrong fragment to the file that holds
    # the id; unwrap (keep the text, drop the link) anything whose id exists nowhere.
    repair_broken_links(tmp)

    # Put the TOC after the front matter so the book doesn't open onto the
    # orphan half-title page sitting between the TOC and the title page.
    reorder_frontmatter_nav(tmp)

    # Copy in + manifest-register the diagram images swapped by enhance_html.
    add_print_diagram_images(tmp, src_dir)

    # Embed + manifest-register the Cinzel title font (cover-echo title pages).
    add_title_font(tmp)

    # Drop pandoc's broken `#toc` landmark so Kindle/KDP stops rejecting the upload.
    fix_nav_landmarks(tmp)

    # Drop TOC entries pointing at display:none targets (the half-title h1) -- the
    # actual cause of Kindle's "table of content could not be built" rejection.
    drop_hidden_toc_entries(tmp)

    # Rezip: mimetype MUST be first and stored uncompressed (EPUB OCF spec).
    os.remove(epub_path)
    with zipfile.ZipFile(epub_path, 'w', zipfile.ZIP_DEFLATED) as z:
        mt = os.path.join(tmp, 'mimetype')
        if os.path.exists(mt):
            z.write(mt, 'mimetype', compress_type=zipfile.ZIP_STORED)
        for root, _, files in os.walk(tmp):
            for fn in sorted(files):
                p = os.path.join(root, fn)
                rel = os.path.relpath(p, tmp)
                if rel == 'mimetype':
                    continue
                z.write(p, rel)
    shutil.rmtree(tmp)
    print(f' epub enhanced ({changed} content docs transformed)')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
