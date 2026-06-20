# Index Data Reference

Index data files live in `editions/1st-edition/content/index-data/`. They are **machine-maintained JSON files** -- the build reads them; humans edit them through purpose-built scripts or a visual editor (for table widths).

---

## Topical index

### `topical-index.json`

**Purpose:** Paragraph-precise locators for the A-Z topical index (Appendix Q). Each entry maps a term to one or more verbatim phrases in the text; the build locates those phrases and resolves them to exact pages (PDF) or section anchors (web/EPUB).

**Schema:** Array of objects.

```json
[
  {
    "term": "Cheung, Vincent",
    "locations": [
      {
        "phrase": "Vincent Cheung, a Clarkian occasionalist, has affirmed outright...",
        "section": "Appendix I"
      }
    ],
    "see_also": ["Clark, Gordon", "Authorship"]
  }
]
```

| Field | Type | Description |
|-------|------|-------------|
| `term` | string | The index headword as it appears in the A-Z listing |
| `locations` | array | One entry per curated location |
| `locations[].phrase` | string | A verbatim text fragment from the manuscript that locates the discussion |
| `locations[].section` | string | The chapter or appendix that contains the phrase (e.g. `"Chapter 15"`, `"Appendix I"`) |
| `see_also` | array | Optional. Related index terms. |

**Regeneration:** No automated regenerator; entries are curated manually or with AI-assist. The precision-baking workflow uses `engine/indexing/reanchor_run.py` (hardens phrase matches) and `engine/indexing/classify_index_anchors.py`.

**Backup files:** `topical-index.json.ai-bak`, `.harden-bak`, `.precision-bak`, `topical-index.pristine-bak.json`, `topical-index.raw.json` -- snapshots from successive precision passes.

---

## Glossary index

### `glossary-index.json`

**Purpose:** Paragraph-precise locators for the glossary's "See Chapter N" cross-references (Appendix R). Works exactly like the topical index: each entry holds curated phrase-locators that the build resolves to exact pages or anchors.

**Schema:** Array of objects (same shape as `topical-index.json`).

```json
[
  {
    "term": "Abba",
    "locations": [
      {
        "phrase": "Abba, Father\" in time (Romans 8:15) is the rendering of what was",
        "section": "Appendix A1"
      }
    ]
  }
]
```

**Regeneration:** `engine/indexing/build_glossary_index.py` -- scans each glossary entry in `appendix-r-glossary.md` for "See Chapter N / Appendix X" pointers, then searches the referenced section for the headword (or its core words) and captures the surrounding verbatim phrase. Run after editing the glossary to keep page refs accurate.

**Important:** After editing `appendix-r-glossary.md` (adding, removing, or changing entries), run `build_glossary_index.py` before building the PDF/EPUB, or new entries will lack precise page references.

**Backup files:** `glossary-index.json.ai-bak`, `.harden-bak`, `.precision-bak`, `glossary-index.pristine-bak.json`, `glossary-index.raw.json`.

---

## Per-trim figure placement

Each figure-placement file maps a figure stem (the image filename without extension) to a move instruction: how many paragraphs to relocate the figure from its authored position. Positive integers move the figure forward; they are trim-specific because reflowing at different page sizes shifts where orphan gaps appear.

### `figure-placement-7x10.json`
### `figure-placement-8.5x11.json`
### `figure-placement-6x9.json`
### `figure-placement-webpdf.json`

**Schema:** Object. Key = figure stem, value = integer offset (number of paragraphs to move).

```json
{ "hegel-schlesinger": 1 }
```

**Regeneration:** Manually, via visual inspection of the built PDF. The `scripts/table-width-editor.py` visual editor in the original PristineGrace project can be adapted; no equivalent tool is in this repo yet.

---

## Per-trim figure overrides

Maps figure stem to a `max-height` cap (in inches as a float). Used to prevent very tall diagrams from consuming too much vertical space on a specific trim.

### `figure-overrides-7x10.json`
### `figure-overrides-8.5x11.json`
### `figure-overrides-6x9.json`
### `figure-overrides-webpdf.json`

**Schema:** Object. Key = figure stem, value = float (max-height in inches).

```json
{ "firmware": 3.6 }
```

---

## Per-trim figure float

Maps figure stem to a float percentage -- how wide the figure occupies when floated left (as a `%` of text block width). A float wraps text around the right side of the figure.

### `figure-float-7x10.json`
### `figure-float-8.5x11.json`
### `figure-float-webpdf.json`

**Schema:** Object. Key = figure stem, value = integer (percentage).

```json
{ "carracci-women-tomb": 50 }
```

---

## Figure anchor (8.5x11 only)

Maps figure stem to a heading name in the same section. The figure is anchored to appear near that heading.

### `figure-anchor-8.5x11.json`

**Schema:** Object. Key = figure stem, value = heading text string.

```json
{ "millennium": "Objections and Answers" }
```

---

## Figure class overrides

Maps figure stem to a CSS class applied to the figure container. Used to assign layout classes like `book-figure-wide`.

### `figure-class-8.5x11.json`

**Schema:** Object. Key = figure stem, value = CSS class string.

```json
{ "creation-nebula": "book-figure-wide" }
```

---

## Verse split

List of scripture references where the build should split a group of verses (e.g. split `Romans 8:15, 16` into two separate verse chips). Used to control "For Further Study" card rendering.

### `verse-split-7x10.json`
### `verse-split-webpdf.json`

**Schema:** Array of strings.

```json
["1 Corinthians 6:9"]
```

---

## Table widths

Maps a table hash key to per-column width percentages. The PDF builder uses these to emit absolute-inch column widths, which are required because weasyprint intermittently renders percentage `<col>` widths as auto/content for some tables in a long document.

### `table-widths.json`

**Schema:** Object. Key = 10-char hex hash, value = object with `label` and `widths` array.

```json
{
  "e730000da7": {
    "label": "Chapter 1: The Sentence",
    "widths": [23.1, 44.1, 17.4, 15.4]
  }
}
```

**Regeneration:** The `table-width-editor.py` script (in the original PristineGrace repo) provides a visual GUI for editing per-column percentages per table. The hash key is computed from the table header content.

---

## Table catalog

An inventory of every table in the book: hash key, label, column count, header row, and first data row. Used as the human-readable index for `table-widths.json` -- it identifies which table a hash corresponds to.

### `table-catalog.json`

**Schema:** Array of objects.

```json
[
  {
    "key": "e730000da7",
    "label": "Chapter 1: The Sentence",
    "ncols": 4,
    "header": ["Clause", "What It Establishes", "Develops In", "Key Scripture"],
    "rows": [[...]]
  }
]
```

**Regeneration:** Regenerated automatically when the table-width editor scans the book source.

---

## Reanchor residue

### `reanchor-residue.json`

Records index locators that could not be precisely anchored (phrase not found in its curated section) after a precision-hardening pass. Used to track and re-audit unresolved entries.

**Schema:** varies; generated by `engine/indexing/reanchor_run.py`.

---

## Notes on the `index-data/` location

In this repo, `index-data/` lives inside `content/` (`editions/1st-edition/content/index-data/`). The engine resolves it as `$BOOK_SOURCE_DIR/index-data`, where `$BOOK_SOURCE_DIR = editions/<ed>/content`. This was a Phase-1 decision to avoid touching the engine's path logic. In Phase 2, when `indexdata_dir` from `edition.toml` goes live, the index-data could be moved to `editions/<ed>/index-data/` (a sibling of `content/`) to reflect the design spec's intent.
