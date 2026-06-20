"""
Cross-reference mapping for "A Thought in the Mind of God".
Generates chapter <-> appendix links with deep links to Appendix A subsections.
Used by build-book.sh (HTML/EPUB) and build-book-pdf.py (PDF).
"""
import re, glob, os, json


def slugify(text):
    """Generate pandoc-style heading ID from text."""
    slug = re.sub(r'[^\w\s.-]', '', text.lower()).strip()  # keep periods (pandoc does): "vs." -> "vs."
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug


def build_appendix_heading_map(book_dir):
    """Build a map of appendix key -> (title, pandoc heading ID).

    Keys are uppercase strings: 'A1'..'A12', 'B', 'C', ..., 'Q'. The applied
    appendices used to be one mega-file ('A'); after the split each sub-appendix
    is its own file and gets its own key in this map.
    """
    heading_map = {}
    for path in sorted(glob.glob(os.path.join(book_dir, "appendix-*.md"))):
        with open(path) as f:
            for line in f:
                m = re.match(r'^#\s+Appendix\s+([A-Z][0-9]*):\s+(.+)', line)
                if m:
                    key = m.group(1).upper()
                    full_title = f"Appendix {key}: {m.group(2).strip()}"
                    slug = slugify(f"appendix-{key.lower()}-{m.group(2).strip()}")
                    heading_map[key] = (full_title, slug)
                    break
    return heading_map


def build_chapter_heading_map(book_dir):
    """Build a map of chapter number -> (title, pandoc heading ID)."""
    heading_map = {}
    for cf in sorted(glob.glob(os.path.join(book_dir, "chapter-[0-9]*.md"))):
        with open(cf) as f:
            for line in f:
                m = re.match(r'^#\s+Chapter\s+(\d+):\s+(.+)', line)
                if m:
                    num = int(m.group(1))
                    full_title = f"Chapter {num}: {m.group(2).strip()}"
                    slug = slugify(f"chapter-{num}-{m.group(2).strip()}")
                    heading_map[num] = (full_title, slug)
                    break
    return heading_map


def build_applied_subsection_map(book_dir):
    """Parse each A1-A12 appendix into its subsections.

    Returns list of (appendix_key, appendix_slug, subsection_title,
    subsection_slug, subsection_text). `appendix_key` is 'A1'..'A12'.
    Subsections are the `## On Topic` (or `## Part N: ...`) headings
    inside each file. The `## A Final Word` closer is skipped.
    """
    out = []
    applied_paths = sorted(glob.glob(os.path.join(book_dir, "appendix-a[0-9]*.md")))
    for path in applied_paths:
        with open(path) as f:
            content = f.read()

        # Find the appendix key and slug from the H1
        key = None
        appendix_slug = None
        for line in content.split('\n'):
            m = re.match(r'^#\s+Appendix\s+(A[0-9]+):\s+(.+)', line)
            if m:
                key = m.group(1).upper()
                appendix_slug = slugify(f"appendix-{key.lower()}-{m.group(2).strip()}")
                break
        if not key:
            continue

        # Parse `##` subsections (including "Part N: ...")
        current_title = None
        current_slug = None
        current_text = []
        for line in content.split('\n'):
            m = re.match(r'^##\s+(.+)', line)
            if m and not line.startswith('###'):
                heading = m.group(1).strip()
                if heading == 'A Final Word':
                    # Flush pending and stop
                    if current_title:
                        out.append((key, appendix_slug, current_title, current_slug, '\n'.join(current_text)))
                    current_title = None
                    current_text = []
                    break
                if current_title:
                    out.append((key, appendix_slug, current_title, current_slug, '\n'.join(current_text)))
                current_title = heading
                current_slug = slugify(heading)
                current_text = []
            elif current_title:
                current_text.append(line)
        if current_title:
            out.append((key, appendix_slug, current_title, current_slug, '\n'.join(current_text)))
    return out


def build_crossref_map(book_dir):
    """Build the full cross-reference map.

    Returns:
        chapter_to_appendices: {ch_num: [(letter, title, slug, [subsections])]}
        appendix_to_chapters: {letter: [(ch_num, ch_title, ch_slug)]}

    For Appendix A, subsections is a list of (subsection_title, subsection_slug).
    For other appendices, subsections is empty.
    """
    # Skip reference appendices that touch everything
    # P/Q/R/S are the reference back matter (Scripture Index, Topical Index,
    # Glossary, Bibliography) -- not content appendices, so they never appear in a
    # chapter's "Related Appendices" list. B/M/N/O are skipped because they touch
    # nearly every chapter (over-linking); they're re-added selectively via overrides.
    SKIP_APPENDICES = {'B', 'M', 'N', 'O', 'P', 'Q', 'R', 'S'}

    app_headings = build_appendix_heading_map(book_dir)
    ch_headings = build_chapter_heading_map(book_dir)

    # --- A1-A12 subsection -> chapter mapping ---
    applied_sections = build_applied_subsection_map(book_dir)
    # ch_num -> [(appendix_key, appendix_slug, sub_title, sub_slug)]
    applied_ch_to_subs = {}
    for key, app_slug, sub_title, sub_slug, text in applied_sections:
        ch_refs = set()
        for m in re.finditer(r'(?:Chapter|Ch\.)\s+(\d+)', text):
            ch_refs.add(int(m.group(1)))
        for ch in ch_refs:
            applied_ch_to_subs.setdefault(ch, []).append((key, app_slug, sub_title, sub_slug))

    # Manual subsection overrides: chapter -> list of (appendix_key, subsection_slug).
    # Matched against the parsed subsections; titles fill in automatically.
    APPLIED_MANUAL = {
        24: [('A5', 'on-ordination'),
             ('A5', 'on-plural-eldership-vs-the-single-pastor'),
             ('A5', 'on-paid-preachers')],
    }
    applied_lookup = {(key, slug): (app_slug, title)
                      for key, app_slug, title, slug, _ in applied_sections}
    for ch_num, entries in APPLIED_MANUAL.items():
        bucket = applied_ch_to_subs.setdefault(ch_num, [])
        existing = {(k, ss) for (k, _, _, ss) in bucket}
        for (key, sub_slug) in entries:
            if (key, sub_slug) in existing:
                continue
            info = applied_lookup.get((key, sub_slug))
            if info:
                app_slug, title = info
                bucket.append((key, app_slug, title, sub_slug))

    # --- Other appendices -> chapter mapping ---
    # Scan each non-applied, non-skipped appendix for chapter references
    app_ch_refs = {}  # key -> set of ch_nums
    for path in sorted(glob.glob(os.path.join(book_dir, "appendix-*.md"))):
        with open(path) as f:
            text = f.read()
        # Extract key from H1
        key = None
        for line in text.split('\n'):
            m = re.match(r'^#\s+Appendix\s+([A-Z][0-9]*):', line)
            if m:
                key = m.group(1).upper()
                break
        if not key:
            continue
        if key in SKIP_APPENDICES:
            continue
        if re.match(r'^A[0-9]+$', key):
            # Applied appendices -- handled above via subsection map
            continue
        ch_refs = set()
        for m in re.finditer(r'(?:Chapter|Ch\.)\s+(\d+)', text):
            ch_refs.add(int(m.group(1)))
        if ch_refs:
            app_ch_refs[key] = ch_refs

    # --- Also scan chapters for appendix references ---
    ch_app_refs = {}  # ch_num -> set of keys
    chapter_files = sorted(glob.glob(os.path.join(book_dir, "chapter-[0-9]*.md")))
    for cf in chapter_files:
        ch_match = re.match(r'chapter-(\d+)', os.path.basename(cf))
        if not ch_match:
            continue
        ch_num = int(ch_match.group(1))
        with open(cf) as f:
            text = f.read()
        body = '\n'.join(l for l in text.split('\n') if not l.startswith('# '))
        for m in re.finditer(r'(?:Appendix|App\.)\s+([A-Z][0-9]*)', body):
            key = m.group(1).upper()
            if key in SKIP_APPENDICES:
                continue
            # Applied appendices are already surfaced through subsection cites;
            # skip broad "Appendix A5" references to avoid duplicates unless the
            # applied-subsection pass missed this chapter entirely.
            if re.match(r'^A[0-9]+$', key):
                continue
            ch_app_refs.setdefault(ch_num, set()).add(key)

    # --- Manual thematic overrides: chapter -> appendix links ---
    # These supplement the automated scan for appendices that are thematically
    # essential to a chapter but don't necessarily cite it by number.
    # N/M/O are on SKIP_APPENDICES (they reference nearly every chapter, so the auto
    # scan would over-link them). Add them back ONLY where a chapter is genuinely,
    # centrally about that appendix's subject -- Appendix N ("The Platonic Floor")
    # for the chapters built on the law of Plato; Appendix O ("The Floor Under This
    # Book") for ch30, which cites it directly.
    MANUAL_OVERRIDES = {
        1:  ['B', 'I', 'J', 'N'],  # Sentence -> Derivation Map, Framework Comparison, Op. Idealism, Platonic Floor
        3:  ['G', 'H', 'J'],       # Bit from God -> Simulation, Quantum Realm, Operational Idealism
        5:  ['D', 'I', 'N'],       # Decrees -> Infra/Supra, Framework Comparison, Platonic Floor (law of Plato)
        6:  ['N'],                 # The Author Steps In -> Platonic Floor (cites Appendix N)
        7:  ['C', 'N'],            # Covenants Not Contracts -> MCT; Platonic Floor (federal headship = law of Plato)
        8:  ['C'],                  # Covenant of Grace -> MCT Distinctives
        9:  ['C', 'F'],             # Progressive Rendering -> MCT Distinctives, Dead Sea Scrolls
        10: ['C'],                  # Covenant Before Ceremony -> MCT Distinctives
        13: ['N'],                 # Satan Created Evil -> Platonic Floor (THE law-of-Plato chapter)
        14: ['K'],                  # Every Sin Same Distance -> Phil Johnson Exchange
        17: ['J'],                  # Thinking About Thinking -> Operational Idealism
        19: ['K'],                  # The Gospel -> Phil Johnson Exchange
        24: ['C'],                  # Women in Ministry -> MCT (participatory ecclesiology)
        25: ['I', 'J'],             # Presuppositionalism -> Framework Comparison, Operational Idealism
        26: ['F'],                  # The Canon -> Dead Sea Scrolls
        28: ['N'],                 # Heaven and Hell -> Platonic Floor (Platonic body-devaluation)
        29: ['H', 'N'],            # Higher Resolution -> Quantum Realm; Platonic Floor (cites Appendix N)
        30: ['K', 'O'],            # Enough for Me -> Phil Johnson Exchange; The Floor Under This Book (cites App. O)
    }

    # --- Build chapter -> appendices map ---
    # Each entry: (appendix_key, appendix_title, appendix_slug, [(sub_title, sub_slug), ...])
    # Non-applied appendices have an empty subsection list.
    chapter_to_appendices = {}
    all_chapters = set(ch_headings.keys())

    def _applied_key_sort(k):
        # Book order: applied A-series first, numeric (so A11 follows A2, not A1),
        # then lettered appendices alphabetically (B..S) -- which IS their order in
        # the book, since appendices are lettered in the sequence they're printed.
        m = re.match(r'^A([0-9]+)$', k)
        return (0, int(m.group(1))) if m else (1, k)

    # Book-order index for applied subsections: their position within each appendix
    # file (applied_sections is parsed in document order), so subsection lists under
    # an appendix render in the order they appear in that appendix, not discovery order.
    sub_order = {(key, sub_slug): idx
                 for idx, (key, _app_slug, _sub_title, sub_slug, _text)
                 in enumerate(applied_sections)}

    for ch_num in sorted(all_chapters):
        entries = []

        # Applied-appendix subsections (grouped per A-N)
        if ch_num in applied_ch_to_subs:
            grouped = {}
            for (key, app_slug, sub_title, sub_slug) in applied_ch_to_subs[ch_num]:
                grouped.setdefault(key, (app_slug, []))[1].append((sub_title, sub_slug))
            for key in sorted(grouped.keys(), key=_applied_key_sort):
                app_slug, subs = grouped[key]
                # Order subsections by their position within the appendix (book order).
                subs.sort(key=lambda s, _k=key: sub_order.get((_k, s[1]), 10**9))
                if key in app_headings:
                    title, _ = app_headings[key]
                else:
                    title = f"Appendix {key}"
                entries.append((key, title, app_slug, subs))

        # Other appendices (from reverse map: appendix references this chapter)
        for key, ch_refs in sorted(app_ch_refs.items()):
            if ch_num in ch_refs and key in app_headings:
                title, slug = app_headings[key]
                entries.append((key, title, slug, []))

        # Also add appendices the chapter explicitly references
        if ch_num in ch_app_refs:
            existing_keys = {e[0] for e in entries}
            for key in sorted(ch_app_refs[ch_num]):
                if key not in existing_keys and key in app_headings:
                    title, slug = app_headings[key]
                    entries.append((key, title, slug, []))

        # Apply manual thematic overrides
        if ch_num in MANUAL_OVERRIDES:
            existing_keys = {e[0] for e in entries}
            for key in MANUAL_OVERRIDES[ch_num]:
                if key not in existing_keys and key in app_headings:
                    title, slug = app_headings[key]
                    entries.append((key, title, slug, []))

        # Sort the whole list into book order: applied A-series (numeric) first,
        # then lettered appendices alphabetically. (Dedup already happened above.)
        entries.sort(key=lambda e: _applied_key_sort(e[0]))

        if entries:
            chapter_to_appendices[ch_num] = entries

    # --- Build appendix -> chapters map ---
    appendix_to_chapters = {}

    # Applied appendices: which chapters do their subsections reference?
    applied_keys_chs = {}
    for (key, _app_slug, _sub_title, _sub_slug, text) in applied_sections:
        for m in re.finditer(r'(?:Chapter|Ch\.)\s+(\d+)', text):
            applied_keys_chs.setdefault(key, set()).add(int(m.group(1)))
    for key, chs in applied_keys_chs.items():
        appendix_to_chapters[key] = sorted([
            (ch, ch_headings[ch][0], ch_headings[ch][1])
            for ch in chs if ch in ch_headings
        ])

    # Other appendices
    for key, ch_refs in sorted(app_ch_refs.items()):
        appendix_to_chapters[key] = sorted([
            (ch, ch_headings[ch][0], ch_headings[ch][1])
            for ch in ch_refs if ch in ch_headings
        ])

    return chapter_to_appendices, appendix_to_chapters


def inject_related_appendices(combined, chapter_to_appendices, link_prefix="#"):
    """Inject Related Appendices blocks after For Further Study in combined markdown.
    Also inject Referenced in Chapters after appendix H1 headings."""
    lines = combined.split('\n')
    new_lines = []
    current_chapter = None
    in_ffs = False
    ffs_start_idx = -1

    for i, line in enumerate(lines):
        # Track which chapter we're in
        ch_m = re.match(r'^# Chapter (\d+):', line)
        if ch_m:
            # If we were in a For Further Study and never found an end marker,
            # inject before this new chapter heading
            if in_ffs and current_chapter and current_chapter in chapter_to_appendices:
                md = generate_chapter_related_md(current_chapter, chapter_to_appendices, link_prefix)
                if md:
                    new_lines.append(md)
            current_chapter = int(ch_m.group(1))
            in_ffs = False

        app_m = re.match(r'^# Appendix ([A-Z][0-9]*):', line)
        if app_m:
            # Same: inject if pending
            if in_ffs and current_chapter and current_chapter in chapter_to_appendices:
                md = generate_chapter_related_md(current_chapter, chapter_to_appendices, link_prefix)
                if md:
                    new_lines.append(md)
            current_chapter = None
            in_ffs = False

        # Detect For Further Study
        if line.strip() == '## For Further Study':
            in_ffs = True

        # Detect end of chapter content: --- (horizontal rule) or page-break div or new H1/H2
        if in_ffs and (
            line.strip() == '---' or
            "page-break" in line or
            (line.startswith('# ') and 'For Further Study' not in line) or
            (line.startswith('## ') and 'For Further Study' not in line)
        ):
            if current_chapter and current_chapter in chapter_to_appendices:
                md = generate_chapter_related_md(current_chapter, chapter_to_appendices, link_prefix)
                if md:
                    new_lines.append(md)
            in_ffs = False

        new_lines.append(line)

    # Handle case where file ends while in FFS
    if in_ffs and current_chapter and current_chapter in chapter_to_appendices:
        md = generate_chapter_related_md(current_chapter, chapter_to_appendices, link_prefix)
        if md:
            new_lines.append(md)

    return '\n'.join(new_lines)


def generate_chapter_related_md(ch_num, chapter_to_appendices, link_prefix=""):
    """Generate markdown for 'Related Appendices' block to inject after For Further Study.

    link_prefix: for web HTML, use '/mind/chapter/'; for PDF/EPUB, use '#'.
    """
    if ch_num not in chapter_to_appendices:
        return ""

    entries = chapter_to_appendices[ch_num]
    lines = ["\n### Related Appendices\n"]

    # One flat, tight list: every appendix is a top-level bullet; any referenced
    # subsections nest as sub-bullets beneath their appendix. Keeping a single
    # list (no bold-paragraph entries) means every appendix renders at the same
    # level across web/PDF/EPUB instead of some reading as un-bulleted headings.
    for key, title, slug, subsections in entries:
        short_title = title.split(': ', 1)[1] if ': ' in title else title
        # Link URL for the appendix itself
        if link_prefix.startswith('/') or link_prefix.startswith('http'):
            app_slug = f"appendix-{key.lower()}"
            href = f"{link_prefix}{app_slug}"
        else:
            href = f"#{slug}"

        lines.append(f"- [Appendix {key}: {short_title}]({href})")

        # Deep-link to each referenced subsection as a nested sub-bullet.
        for sub_title, sub_slug in subsections:
            if link_prefix.startswith('/') or link_prefix.startswith('http'):
                sub_href = f"{link_prefix}appendix-{key.lower()}#{sub_slug}"
            else:
                sub_href = f"#{sub_slug}"
            lines.append(f"    - [{sub_title}]({sub_href})")

    # Trailing blank line closes the tight list and prevents pandoc from treating
    # a following --- as a setext heading.
    lines.append("")
    lines.append("")

    return '\n'.join(lines)


def generate_appendix_related_md(letter, appendix_to_chapters, link_prefix=""):
    """Generate markdown for 'Referenced in' block to inject at the top of an appendix."""
    if letter not in appendix_to_chapters:
        return ""

    chapters = appendix_to_chapters[letter]
    if not chapters:
        return ""

    ch_links = []
    for ch_num, ch_title, ch_slug in chapters:
        short = ch_title.split(': ', 1)[1] if ': ' in ch_title else ch_title
        if link_prefix.startswith('/') or link_prefix.startswith('http'):
            href = f"{link_prefix}chapter/{ch_num}"
        else:
            href = f"#{ch_slug}"
        ch_links.append(f"[{ch_num}]({href})")

    return f"\n> *Referenced in Chapters {', '.join(ch_links)}*\n"


if __name__ == "__main__":
    import sys
    book_dir = sys.argv[1] if len(sys.argv) > 1 else "."

    ch_map, app_map = build_crossref_map(book_dir)

    # Output as JSON for debugging
    print(json.dumps({
        "chapter_to_appendices": {
            str(k): [(l, t, s, subs) for l, t, s, subs in v]
            for k, v in ch_map.items()
        },
        "appendix_to_chapters": {
            k: [(n, t, s) for n, t, s in v]
            for k, v in app_map.items()
        }
    }, indent=2))
