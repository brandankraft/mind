# Overview

This repo (`Mind2`, renamed to `Mind` at cutover) is the self-contained build system for *A Thought in the Mind of God*. It turns the book's source markdown into seven output formats: web HTML, web PDF, EPUB, and four IngramSpark print interiors (7x10 color, 7x10 B&W, 8.5x11, 6x9).

## Repository layout

```
mind/
├── README.md
├── .gitignore              -- excludes output/, __pycache__, large print files
├── engine/                 -- shared build system (reusable across editions and future books)
│   ├── build.sh            -- single entrypoint: build.sh <edition> <format>
│   ├── build-book.sh       -- orchestrator (1,325 lines): runs the full pipeline per mode
│   ├── build-book-pdf.py   -- PDF/EPUB content builder (3,156 lines): 3-pass index resolution
│   ├── epub_enhance.py     -- EPUB post-processor: parity transforms + KDP-safe fixes
│   ├── build-all-parallel.sh  -- launches multiple format builds concurrently
│   ├── transforms/         -- HTML semantic transforms (15 scripts)
│   ├── indexing/           -- index/glossary/scripture builders (9 scripts)
│   ├── lib/                -- shared helpers (config.sh, crossrefs.py, footnote_refs.py, etc.)
│   ├── assets/             -- static assets the engine needs (diagram HTML partials, DSS paper bg)
│   ├── data/               -- engine data files (kjv.json for scripture lookups)
│   ├── fonts/              -- embedded fonts (Cinzel, CrimsonPro, aAtmospheric)
│   └── templates/          -- (reserved; diagram partials are in assets/)
│   -- top-level engine utilities (add_reading_times.py, audit_pdf.py, extract_glossary.py,
│      inject_web_index.py, inject_epub_index.py, inject_web_glossary.py,
│      inject_epub_glossary.py, optimize_figures.py, prebake_print_images.py,
│      white_space_audit.py, verify_book_build.py, verify_web_links.py,
│      add_chapter_teasers.py, add_red_letter_markers.py, build_commentary.py,
│      diagram_images.py [also in lib/], extract_glossary.py)
├── editions/
│   └── 1st-edition/
│       ├── config/         -- edition.toml + one .toml per output format
│       ├── content/        -- all source markdown, images, front-matter/, ingramspark/, covers/
│       ├── index-data/     -- per-trim tuning JSONs and precision index data
│       ├── static-chapters/ -- hand-maintained HTML for book front/back matter (cover, copyright, etc.)
│       └── output/         -- gitignored; built artifacts land here
├── docs/                   -- this documentation
└── tools/
    ├── verify.sh           -- byte-compare new builds against golden baseline
    ├── normalize_pdf.py    -- strips PDF timestamps for deterministic comparison
    └── normalize_epub.sh   -- strips EPUB timestamps for deterministic comparison
```

## Edition, version, and format -- three distinct axes

**Edition** = a subfolder under `editions/`. Each edition is fully self-contained (its own content, images, index-data, config, output). The 1st edition is `editions/1st-edition/`. A 2nd edition would be a sibling folder.

**Version within an edition** = tracked by git (history + tags). To reproduce an older revision, `git checkout <tag>` and build. The `version` key in `edition.toml` stamps every artifact filename (e.g. `a-thought-in-the-mind-of-god-1.0-web-pdf.pdf`).

**Output format** = which rendering the build produces. Seven formats, each with its own config file:

| Format | Config file | Output |
|--------|-------------|--------|
| `web-html` | `web-html.toml` | Chapter HTML files + `chapters.json` (served at pristinegrace.org) |
| `web-pdf` | `web-pdf.toml` | Digital download PDF (7x10 geometry, color, covers, popover footnotes) |
| `epub` | `epub.toml` | EPUB3 for Kindle and e-readers |
| `7x10-color` | `7x10-color.toml` | IngramSpark 7x10 color hardcover interior |
| `7x10-bw` | `7x10-bw.toml` | IngramSpark 7x10 B&W interior |
| `8.5x11` | `8.5x11.toml` | IngramSpark 8.5x11 hardcover interior |
| `6x9` | `6x9.toml` | IngramSpark 6x9 B&W paperback interior |

## Quickstart

```bash
# Build one format
engine/build.sh 1st-edition web-html

# Build all formats sequentially (note: 'all' mode not yet wired in build.sh; run each separately)
for fmt in web-html web-pdf epub 7x10-color 7x10-bw 8.5x11 6x9; do
    engine/build.sh 1st-edition $fmt
done
```

**Dependencies:** pandoc, weasyprint, pypdf (Python), Pillow (Python).

Built artifacts land in `editions/1st-edition/output/<format>/` with version-stamped filenames. `output/` is gitignored -- artifacts are published as GitHub Releases, not committed.

## Phase 1 vs Phase 2

This repo was built under a two-phase strategy. **Phase 1** (current) = byte-identical relocation. The engine is a copy of the original build scripts from PristineGrace, running against the 1st-edition content via config-resolved paths. No build logic changed; output is byte-identical to the original. **Phase 2** (future) = deep genericization: per-format config knobs (margins, notes mode, whitespace inserts, image-variant selection) go live, making the engine truly pluggable. Phase-2 keys exist in the TOML files but are not yet read by the engine. See `config-reference.md` for which keys are Phase-2.
