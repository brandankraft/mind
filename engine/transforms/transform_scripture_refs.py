#!/usr/bin/env python3
"""
Tint parenthetical Scripture references in body prose, e.g. "(John 1:1)" or
"(Isa. 45:7; Rom. 9:22-23)", by wrapping the reference text in
<span class="vref">. CSS gives .vref a subtle accent colour so citations read
as anchors without shouting.

Deliberately conservative:
  * ONLY parenthetical references match -- bare inline mentions ("Isaiah 45")
    are left alone, so index entries / prose names are never touched.
  * Tag-aware: a skip-stack suppresses matching inside <a>, headings (h1-h6),
    <pre>/<code>, and the two index appendices' .index-columns blocks, so we
    never wrap inside an existing link, anchor, or reference list.
  * Wraps text only -- it never changes the document's text content, so index
    page-resolution and named-destination links are unaffected. Run LAST.
"""
import re

# Canonical book names + the abbreviations actually used in the book.
_BOOKS = [
    "Genesis","Gen","Exodus","Exod","Exo","Ex","Leviticus","Lev","Numbers","Num",
    "Deuteronomy","Deut","Joshua","Josh","Judges","Judg","Ruth",
    "Samuel","Sam","Kings","Kgs","Ki","Chronicles","Chron","Chr","Ezra",
    "Nehemiah","Neh","Esther","Esth","Job","Psalms","Psalm","Pss","Ps",
    "Proverbs","Prov","Ecclesiastes","Eccles","Eccl","Song of Solomon","Song","Canticles","Cant",
    "Isaiah","Isa","Jeremiah","Jer","Lamentations","Lam","Ezekiel","Ezek",
    "Daniel","Dan","Hosea","Hos","Joel","Amos","Obadiah","Obad","Jonah","Jon",
    "Micah","Mic","Nahum","Nah","Habakkuk","Hab","Zephaniah","Zeph","Haggai","Hag",
    "Zechariah","Zech","Malachi","Mal",
    "Matthew","Matt","Mt","Mark","Mk","Luke","Lk","John","Jn","Acts",
    "Romans","Rom","Corinthians","Cor","Galatians","Gal","Ephesians","Eph",
    "Philippians","Phil","Colossians","Col","Thessalonians","Thess","Thes",
    "Timothy","Tim","Titus","Tit","Philemon","Phlm","Philem","Hebrews","Heb",
    "James","Jas","Peter","Pet","Jude","Revelation","Rev",
]
# Longest-first so "Song of Solomon" wins over "Song"; escape for regex.
_BOOK_ALT = "|".join(re.escape(b) for b in sorted(_BOOKS, key=len, reverse=True))
# One reference: optional 1-3/First.. prefix, book, optional '.', space, c:v with
# ranges and comma/semicolon lists.
_REF = (r"(?:[1-3]\s)?(?:" + _BOOK_ALT + r")\.?\s\d{1,3}:\d{1,3}"
        r"(?:[–\-]\d{1,3})?(?:[,;]\s?\d{1,3}(?::\d{1,3})?(?:[–\-]\d{1,3})?)*")
# A whole parenthetical that is ONLY references (possibly several, ; or , joined).
_PAREN_RE = re.compile(r"\((" + _REF + r"(?:\s*[;,]\s*" + _REF + r")*)\)")

_TAG_RE = re.compile(r"(<[^>]+>)")
# Elements whose text we must NOT touch.
_SKIP_OPEN = re.compile(r"<(a|h[1-6]|pre|code|script|style)\b", re.I)
_SKIP_CLOSE = re.compile(r"</(a|h[1-6]|pre|code|script|style)\s*>", re.I)
_INDEX_OPEN = re.compile(r'<div[^>]*class="[^"]*index-columns', re.I)


def transform_html(html):
    out = []
    skip = 0
    div_depth = 0
    index_div_depth = None
    count = 0
    for tok in _TAG_RE.split(html):
        if not tok:
            continue
        if tok.startswith("<"):
            # Track index-columns region by div nesting.
            if tok.startswith("<div") or tok.startswith("<DIV"):
                div_depth += 1
                if index_div_depth is None and _INDEX_OPEN.match(tok):
                    index_div_depth = div_depth
            elif _SKIP_CLOSE.match(tok) is None and re.match(r"</div\s*>", tok, re.I):
                if index_div_depth is not None and div_depth == index_div_depth:
                    index_div_depth = None
                div_depth -= 1
            if _SKIP_OPEN.match(tok) and not tok.rstrip().endswith("/>"):
                skip += 1
            elif _SKIP_CLOSE.match(tok):
                skip = max(0, skip - 1)
            out.append(tok)
        else:
            if skip > 0 or index_div_depth is not None:
                out.append(tok)
            else:
                def repl(m):
                    nonlocal count
                    count += 1
                    return '(<span class="vref">' + m.group(1) + "</span>)"
                out.append(_PAREN_RE.sub(repl, tok))
    return "".join(out), count
