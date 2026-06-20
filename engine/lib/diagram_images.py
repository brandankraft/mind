"""Swap specific CSS-generated diagrams for pre-rendered image figures.

Used by the PDF and EPUB builds ONLY -- the web build keeps the live CSS
diagrams (selectable, and they reflow on phones). For print and e-readers we
substitute light-background PNGs that live in the book source dir, rendered as
wide centered figures (~85% of the text block).

Each image is keyed to exactly one diagram instance:
  * eternal-thought-diagram      -> eternal_thought_light.png   (unique)
  * cognition-cascade (ch 2)     -> god_thinks_light.png        (no "firmware fires")
  * cognition-cascade (App. E)   -> god_thinks_app_e_light.png  (has "firmware fires")
  * lineage-diagram              -> lineage_light.png           (also strips the
                                    duplicate <h2 class="lineage-heading"> since the
                                    image carries its own title)
"""
import re

ETERNAL_THOUGHT_IMG = "eternal_thought_light.png"
GOD_THINKS_IMG = "god_thinks_light.png"
GOD_THINKS_APP_E_IMG = "god_thinks_app_e_light.png"
LINEAGE_IMG = "lineage_light.png"

# Files copied into the EPUB media dir when swapping (PDF reads them straight from
# the book source dir via weasyprint's --base-url).
IMAGE_FILES = [ETERNAL_THOUGHT_IMG, GOD_THINKS_IMG, GOD_THINKS_APP_E_IMG, LINEAGE_IMG]


def _figure(src, alt, img_style=""):
    style = f' style="{img_style}"' if img_style else ""
    return (f'<figure class="book-figure-wide">'
            f'<img src="{src}" alt="{alt}"{style}/></figure>')


def _replace_balanced_div(html, class_name, replacement):
    """Replace the first <div class="class_name" ...> ... matching </div> with
    replacement, correctly skipping nested <div>s. Returns (html, count)."""
    open_re = re.compile(r'<div\b[^>]*\bclass="' + re.escape(class_name) + r'"[^>]*>')
    m = open_re.search(html)
    if not m:
        return html, 0
    depth = 1
    for tag in re.finditer(r'<(/?)div\b[^>]*>', html[m.end():]):
        depth += -1 if tag.group(1) else 1
        if depth == 0:
            end = m.end() + tag.end()
            return html[:m.start()] + replacement + html[end:], 1
    return html, 0  # unbalanced -- leave untouched


def _replace_cascades(html, img_prefix):
    """Replace BOTH cognition-cascade <ol>s, each with its own image: the
    'firmware fires' one (Appendix E) -> god_thinks_app_e; the other (ch 2) ->
    god_thinks."""
    count = 0

    def repl(m):
        nonlocal count
        block = m.group(0)
        if "firmware fires" in block:
            img, alt = GOD_THINKS_APP_E_IMG, "The perception cascade: God's thought to theology and back"
        else:
            img, alt = GOD_THINKS_IMG, "The cognition cascade: God's thought to theology and back"
        count += 1
        # God Thinks cascade plates are 1254x1254 squares that otherwise fill the
        # full text width; shrink them 33% (to 67%) per Brandan. Only these two.
        return _figure(img_prefix + img, alt, img_style="max-width:67%")

    html = re.sub(r'<ol\b[^>]*\bcognition-cascade\b[^>]*>.*?</ol>',
                  repl, html, flags=re.S)
    return html, count


def swap_print_diagrams(html, img_prefix=""):
    """Swap the eternal-thought, both cognition-cascades, and the lineage diagram
    for image figures.

    img_prefix is prepended to each filename: "" for the PDF (weasyprint resolves
    relative to the book source dir), "../media/" for the EPUB content docs.
    Returns (html, total_swaps).
    """
    total = 0

    html, c = _replace_balanced_div(
        html, "eternal-thought-diagram",
        _figure(img_prefix + ETERNAL_THOUGHT_IMG, "The Eternal Thought", img_style="max-width:67%"))
    total += c

    html, c = _replace_cascades(html, img_prefix)
    total += c

    # Lineage: the image carries its own title, so drop the duplicate heading.
    html = re.sub(r'<h2[^>]*\bclass="lineage-heading"[^>]*>.*?</h2>\s*', '', html, flags=re.S)
    html, c = _replace_balanced_div(
        html, "lineage-diagram",
        _figure(img_prefix + LINEAGE_IMG, "Where this book stands in the tradition"))
    total += c

    return html, total
