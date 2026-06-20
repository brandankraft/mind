# Build Pipeline

## Entry point: `engine/build.sh`

```
engine/build.sh <edition> <format>
```

1. Sources `engine/lib/config.sh` -> calls `load_config <edition> <format>`.
2. `load_config` reads `editions/<ed>/config/edition.toml` (for `VERSION`) and `editions/<ed>/config/<format>.toml` (for `build_flag`). Exports `BOOK_SOURCE_DIR`, `OUTPUT_DIR`, `FORMAT_FLAG`, `ARTIFACT_EXT`, `VERSION`.
3. Creates `$OUTPUT_DIR` if it doesn't exist.
4. For `web-html`: creates a scratch dir, pre-populates it with static HTML from `editions/<ed>/static-chapters/`, invokes `engine/build-book.sh --source $BOOK_SOURCE_DIR --web`, then flattens the scratch output into `OUTPUT_DIR`.
5. For all other formats: sets `OUTPUT_DIR` and `BOOK_SOURCE_DIR` in the environment and invokes `engine/build-book.sh --source $BOOK_SOURCE_DIR $FORMAT_FLAG`.
6. Copies the built artifact into `$OUTPUT_DIR` with a version-stamped name (e.g. `a-thought-in-the-mind-of-god-1.0-web-pdf.pdf`).

`FORMAT_FLAG` is read from the `build_flag` key in the format's TOML; if absent, the script falls back to a hardcoded map:

| Format | build_flag |
|--------|-----------|
| web-html | `--web` |
| web-pdf | `--pdf` |
| epub | `--pdf` |
| 7x10-color | `--7x10` |
| 7x10-bw | `--7x10bw` |
| 8.5x11 | `--ingram` |
| 6x9 | `--6x9` |

Note: `web-pdf` and `epub` both use `--pdf`; the PDF builder builds both in a single run.

---

## Orchestrator: `engine/build-book.sh`

1,325-line bash script. Accepts `--web`, `--pdf`, `--ingram`, `--7x10`, `--7x10bw`, `--6x9`, `--all`, and `--source DIR`. Modes compose (`--web --pdf` builds both). No mode = `--web --pdf --ingram` (back-compat default).

### Mode: `--web` (web HTML)

Produces: per-chapter HTML files + `chapters.json`.

**Steps in order:**

1. Counts chapters, appendices, front-matter files in `$BOOK_SOURCE_DIR`.
2. Generates `book-crossref.json` (chapter <-> appendix cross-reference map) via `engine/lib/crossrefs.py`.
3. Processes static front-matter HTML pages (cover, title-page, about, copyright, dedication) from `$OUTPUT_DIR/chapters/` into `chapters.json` if they exist.
4. Runs `process_chapter()` for each prose page in reading order: Foreword, Preface, Acknowledgments, Prologue, How This Book Talks, chapters 1-30, Epilogue, Afterword, appendices (A1-A12 numeric, then B-S), About the Author, Grace and Peace. Static back-cover also appended if present.
   - Each call: strips YAML frontmatter, runs pandoc (`markdown+smart -> html5`), converts en dashes to em dashes, injects Related Appendices cross-reference block.
5. Writes `chapters.json` (with chapter slugs, titles, parts, section headings, sub-sections).
6. Builds a topical-heading map (heading IDs + positions per chapter) for anchor-precise index linking.
7. Links index references (Ch. N, App. X, Prologue/Preface/Epilogue text) in the appendix index pages.

**Post-build HTML transforms** (all `transforms/` scripts; operate on `$OUTPUT_DIR/chapters/*.html`):

| Script | What it does |
|--------|-------------|
| `transform_cascades.py` | Rewrites "God thinks -> ... -> theology" ASCII chains as styled vertical loop visualizations |
| `transform_code_blocks.py` | Styles `// text` comments in code blocks as `<span class="code-comment">` |
| `transform_video_embeds.py` | Injects YouTube `<iframe>` embeds (web-only) |
| `transform_dss_cards.py` | Wraps Dead Sea Scrolls block quotes as styled `.dss-card` components |
| `transform_song_links.py` | Injects PG Music song chips |
| `transform_web_only_images.py` | Inserts web-only images (e.g. the Darth Vader image in Ch 19) |
| `transform_lineage_diagram.py` | Rewrites the Plato/Augustine/Tradition/This Book ASCII in Appendix I as a styled vertical timeline |
| `transform_sentence_breakdown.py` | Rewrites THE SENTENCE radial ASCII in Appendix B as a styled breakdown |
| `transform_eternal_thought_diagram.py` | Rewrites the eternal-thought/cross/conversion/judgment ASCII tree in Ch 2 as styled hero+frame cards |
| `transform_book_tree.py` | Rewrites the file-tree ASCII in "How This Book Talks" as a styled code-editor sidebar |
| `transform_costume_cards.py` | Tags Appendix N costume paragraphs with kind classes for 4-field diagnostic cards |
| `transform_objection_cards.py` | Wraps each objection+answer pair in "Objections and Answers" sections as a single card |
| `transform_study_cards.py` | Converts "For Further Study" verse lists into study cards with verse chips |
| `transform_pullquotes.py` | Tags short blockquotes as `.pullquote` for display-style emphasis |
| `transform_anchor_verses.py` | Callouts paragraphs containing THE SENTENCE's four anchor verses |

**Additional post-build steps:**

- `engine/lib/footnote_refs.py`: links `word*` footnote markers to `<p>* ...` notes (web: jump links; PDF: page pointers).
- `engine/add_reading_times.py`: annotates `chapters.json` with `word_count` and `read_time_minutes`.
- `engine/add_chapter_teasers.py`: annotates `chapters.json` with first-sentence `teaser` per chapter.
- `engine/extract_glossary.py`: extracts Appendix R glossary into a JSON map for runtime tooltip lookup.
- Image copy + web-variant rewriting: for each inline image, prefers `{stem}-web.jpg` over the original; rewrites `src` in HTML to `/book-content/images/{web_variant}?v={filesize}`.
- `engine/inject_web_index.py`: stamps `<span id="ix-...">` anchors into section HTML and rebuilds `appendix-q.html` as a paragraph-precise, linked A-Z topical index.
- `engine/inject_web_glossary.py`: stamps `<span id="glx-...">` anchors and rewrites glossary "See Chapter N" refs as deep links.
- Appendix C table post-processing: `sed` merges the `#` and Distinctive columns, updates colgroup widths.

---

### Mode: `--pdf` (EPUB + web download PDF)

Produces: `$BOOK_SOURCE_DIR/A-Thought-in-the-Mind-of-God.epub` and `.pdf`, then copies both into `$OUTPUT_DIR/downloads/`.

**EPUB steps:**

1. Assembles combined markdown in reading order: strips frontmatter from each file, concatenates. Appendix files are collected A1-A12 numerically then B-Z alphabetically.
2. Inlines cross-reference links (Chapter N / App. X references become pandoc-flavored wikilinks in the combined markdown).
3. Injects Related Appendices blocks via `engine/lib/crossrefs.py`.
4. Rewrites `<img src="foo.png">` to prefer `-web.jpg` variants; falls back to `-light.*` for diagrams (dark-for-screen originals get a light variant for the paper-white EPUB).
5. `engine/inject_epub_index.py`: stamps `[]{#ix-...}` anchors into the combined markdown and replaces Appendix Q body with a linked A-Z index. Pandoc later rewrites cross-file `#ix-...` links to the correct split file.
6. `engine/inject_epub_glossary.py`: stamps `glx-*` anchors and rewrites glossary cross-refs.
7. Runs pandoc: `markdown+smart -> epub3`, `--toc --toc-depth=1 --split-level=1`, with cover image and metadata.
8. `engine/epub_enhance.py`: post-processes the built EPUB in place (see EPUB-specific steps below).

**PDF steps:**

`engine/build-book-pdf.py` (3-pass renderer). See PDF-specific section below.

---

### Mode: `--ingram` (8.5x11 hardcover interior)

Invokes `build-book-pdf.py ... --ingram`. Produces `$BOOK_SOURCE_DIR/ingramspark/A-Thought-in-the-Mind-of-God-8.5x11-hardcover.pdf`. Interior-only (no covers). Even page count enforced for print binding.

### Mode: `--7x10` (7x10 color interior)

Invokes `build-book-pdf.py ... --7x10`. Produces `ingramspark/...-7x10.pdf`.

### Mode: `--7x10bw` (7x10 B&W interior)

Invokes `build-book-pdf.py ... --7x10bw`. Same geometry and pagination as the 7x10 color; all colors grayscaled. Produces `ingramspark/...-7x10-bw.pdf`.

### Mode: `--6x9` (6x9 B&W paperback interior)

Invokes `build-book-pdf.py ... --6x9`. Produces `ingramspark/...-6x9.pdf`. 10.5pt body (vs 11pt for 7x10/8.5x11), B&W only (color 6x9 exceeds IngramSpark page caps).

---

## PDF builder: `engine/build-book-pdf.py`

3,156-line Python script. Three passes.

### Pass 2 (resolution PDF)

`build_combined_v2(all_files, q_placeholder=True)` -- builds the combined markdown with:
- Frontmatter swaps (preface signature image, edition statement, index intros)
- Cross-reference injection (Related Appendices)
- Image variant swapping (print variants for print modes, web variants for digital PDF)
- Figure relocation (`figure-placement-*.json`), figure anchoring, figure float, figure classes
- Appendix Q rendered as a 1-line stub (avoids the expensive 8,000-entry list in this pass)
- The combined markdown converted via pandoc, then HTML transforms applied

Renders to `$BOOK_TMP/book-pass2.pdf` via weasyprint. This PDF is the page-number source for pass 3: its body pagination is identical to the final build, so page numbers resolved here are exact.

Diagram images (`diagram_images.py`) are also applied in pass 2, because the CSS-to-image swap changes page heights and would otherwise make every resolved page number land one early.

### Pass 3 (index resolution)

Searches pass-2 PDF for each locator phrase from `index-data/topical-index.json`, `index-data/glossary-index.json`, and the scripture index. For each:
- `build_section_ranges()` maps each chapter/appendix to its page range in pass 2.
- Each locator phrase is searched within its curated section's page range (scoped to prevent a common word from resolving to the wrong chapter).
- Resolved page numbers are deduplicated per index entry.
- Falls back to section start page if the phrase isn't found (phrase in diagram/table/code block text that doesn't extract).

Also resolves glossary `See Chapter N` cross-refs to precise pages.

### Final pass (pass 3 = the output PDF)

`build_combined_v2(all_files, all_replacements=resolved_pages)` -- same as the resolution pass but with real page numbers substituted and Appendix Q fully rendered.

HTML transforms applied to the final HTML:

| Transform | When applied |
|-----------|-------------|
| `diagram_images.swap_print_diagrams()` | All modes: swaps CSS diagrams (eternal-thought, god-thinks, cascades, lineage) for pre-rendered image figures |
| `stamp_guide_words()` + `detect_opener_splits()` + `apply_opener_splits()` | Print interiors only: adds dictionary-style guide words to back-matter index/glossary openers |
| `inline_pdf_footnotes()` | All modes: converts pandoc footnotes to weasyprint `float:footnote` blocks |
| `add_glossary_xref_pages()` | All modes: rewrites glossary "See Chapter N" with precise page number |
| Semantic transforms (DSS cards, pull-quotes, anchor-verse callouts, objection cards, study cards, cascades, etc.) | All modes: same transforms as web, but applied inline in the PDF HTML |

**PDF assembly:**

- Print interiors: uses `PdfWriter(clone_from=content_pdf)` to preserve the `/Names/Dests` name tree (required for TOC + cross-reference links to resolve). Appends a blank page if the count is odd. Runs `downsample_print_images()` to bring all rasters to ~300 ppi for IngramSpark.
- Digital PDF (web-pdf): renders front cover + back cover as separate weasyprint PDFs, then merges with the content PDF using pypdf (`clone_from`). Named destinations are preserved for working TOC/index links.

**B&W treatment** (7x10-bw, 6x9):
- All CSS colors (hex + rgb/rgba) converted to luminance gray (NTSC weights): `_grayscale_doc()`.
- All `<img>` references swapped to `-bw` variants generated on demand via Pillow: `_grayscale_images()`.

**Prebaked print images:** `engine/prebake_print_images.py` pre-resizes images to ~320 ppi at their printed size and stores them in `content/print-sized/`. The PDF builder uses these via `_print_sized()` to avoid weasyprint embedding full-resolution originals.

---

## EPUB post-processor: `engine/epub_enhance.py`

Applied after pandoc builds the EPUB. Extracts the zip, processes each `.xhtml` content file, repacks.

| Function | What it does |
|----------|-------------|
| `enhance_html()` | Runs DSS cards, pull-quotes, lineage diagram, sentence breakdown, eternal thought, book tree, cascades, objection cards, study cards transforms on each chapter file; makes wide tables responsive |
| `footnote_refs.process_html()` | Links asterisk footnote markers to their notes |
| `diagram_images.swap_print_diagrams()` | Swaps CSS diagrams for pre-rendered image figures (light-background versions for EPUB) |
| `link_cross_file_anchors()` | Retargets bare `#ix-*` links (topical index) to `file.xhtml#ix-*` (pandoc leaves them as bare fragments) |
| `repair_internal_links()` | Fixes cross-ref slug mismatches (cross-ref slugs drop periods that pandoc keeps in heading IDs) |
| `repair_broken_links()` | Catch-all: retargets any remaining broken `<a>` links; unwraps links whose target ID doesn't exist anywhere (prevents KDP rejection) |
| `reorder_frontmatter_nav()` | Moves the TOC after the front matter so the book doesn't open on the half-title |
| `add_print_diagram_images()` | Copies diagram image files into the EPUB and adds them to the manifest |
| `add_title_font()` | Embeds Cinzel font files for the styled title pages |
| `fix_nav_landmarks()` | Drops pandoc's `#toc` landmark (KDP rejects it as a broken link) |
| `drop_hidden_toc_entries()` | Drops TOC entries pointing at `display:none` targets (the half-title h1 -- root cause of Kindle's E24010/E24001 rejection) |

---

## Per-format custom build step summary

| Format | Custom steps |
|--------|-------------|
| `web-html` | All 15 `transforms/` scripts; `inject_web_index.py`; `inject_web_glossary.py`; reading times; chapter teasers; glossary JSON extract; web image variant rewriting; Appendix C table merge |
| `web-pdf` | `_swap_to_web_variants()`; covers merged; no guide words; no grayscale; `inline_pdf_footnotes()`; `diagram_images` swap; `downsample_print_images()` NOT run |
| `epub` | All `epub_enhance.py` passes; `inject_epub_index.py`; `inject_epub_glossary.py`; EPUB CSS injected; font embedding |
| `7x10-color` | Print variants (`_swap_to_print_variants()`); guide words; `stamp_guide_words()`; `downsample_print_images()` |
| `7x10-bw` | Same as 7x10-color + `_grayscale_doc()` + `_grayscale_images()` |
| `8.5x11` | Same as 7x10-color (different page dimensions and margins hardcoded in the script) |
| `6x9` | Same as 7x10-bw (10.5pt body size; 6x9 trim dimensions) |

---

## Parallel builds: `engine/build-all-parallel.sh`

Wraps multiple `build-book.sh` invocations as background jobs, each with its own `BOOK_TMP` scratch dir. Waits for all, reports PASS/FAIL per format. Usage:

```bash
engine/build-all-parallel.sh --7x10 --6x9 --ingram
```

Note: this script drives the old `build-book.sh` flags directly; `engine/build.sh` (the new thin entrypoint) is the recommended interface when building via the edition/format model.
