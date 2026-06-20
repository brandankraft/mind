# Config Reference

Configuration is in TOML. Two tiers: one edition-wide file plus one file per output format. Both live in `editions/<edition>/config/`.

---

## `edition.toml` -- edition-wide settings

Read by `engine/lib/config.sh` at build time. All keys are active in Phase 1.

```toml
title    = "A Thought in the Mind of God"
subtitle = "A Systematic Theology"
author   = "Brandan Kraft"
publisher = "Pristine Grace Publishing"
version  = "1.0"           # stamped into every output artifact filename

# ISBNs (used for metadata; not currently injected by the engine automatically)
isbn_paperback_7x10      = "..."
isbn_hardcover_bw_7x10   = "..."
isbn_hardcover_color_7x10 = "..."
isbn_hardcover_color_8x11 = "..."
isbn_ebook               = "..."

# Directory names, relative to the edition root (editions/<edition>/)
content_dir   = "content"        # source markdown, images, etc.
output_base   = "output"         # output/<format>/ lands here
indexdata_dir = "content/index-data"   # per-trim JSONs

# Output filename pattern (tokens: {slug}, {version}, {format})
output_pattern = "{slug}-{version}-{format}"
slug = "a-thought-in-the-mind-of-god"
```

### Key notes

- `version` is the only key `config.sh` currently reads (via `tomllib`). The engine uses it to version-stamp artifact names.
- `content_dir`, `output_base`, `indexdata_dir` are present for Phase-2 use; the engine currently resolves paths by convention (`editions/<ed>/content/`, `editions/<ed>/output/<fmt>/`).
- `isbn_*` keys document the ISBNs. The engine does not inject them into outputs today; Phase 2 would wire them into PDF metadata.

---

## Per-format files

Each format file inherits from `edition.toml` conceptually (via `extends = "edition"`). The only key the engine currently reads is `build_flag`.

### Active keys (Phase 1 -- read by the engine)

| Key | Type | Purpose |
|-----|------|---------|
| `extends` | string | Convention marker; always `"edition"`. Not parsed by `config.sh`. |
| `format` | string | The format name (matches the filename stem, e.g. `"7x10-color"`). Not read by engine yet. |
| `trim` | string | The physical trim size. Not read by engine yet. |
| `color` | bool | Whether this format is color. Not read by engine yet. |
| `build_flag` | string | **Read by `config.sh`.** The flag passed to `build-book.sh` (e.g. `"--7x10"`). |
| `isbn` | string | The per-format ISBN. Not read by engine yet. |

### Phase-2 keys (present but NOT read by the engine in Phase 1)

These keys are defined in the TOML files as commented-out stubs. They establish the Phase-2 vocabulary without breaking Phase-1 output. **Do not rely on these keys having any effect until Phase 2 is implemented.**

| Key | Phase-2 intent |
|-----|---------------|
| `headers` | Running-head style (`"ingram"`, `"web-pdf"`, `"epub"`, `"web"`, `"none"`) |
| `notes_mode` | Footnote rendering (`"footnote"` = bottom-of-page, `"endnote"` = end-of-chapter, `"popover"` = web hover) |
| `image_variant` | Which image variant to prefer (`"web"`, `"print"`, `"light"`) |
| `figure_tuning` | Which per-trim figure-tuning JSON to apply (e.g. `"7x10"`, `"8.5x11"`, `"none"`) |
| `hooks.post_html` | List of named hook steps to run at the post-HTML stage |
| `hooks.pre_render` | List of named hook steps to run at the pre-render stage |

---

## Per-format file contents (current state)

### `web-html.toml`
```toml
extends = "edition"
format  = "web-html"
trim    = "web"
color   = true
build_flag = "--web"
# Phase-2 knobs commented out
```

### `web-pdf.toml`
```toml
extends = "edition"
format  = "web-pdf"
trim    = "7x10"
color   = true
build_flag = "--pdf"
```

### `epub.toml`
```toml
extends = "edition"
format  = "epub"
trim    = "reflowable"
color   = true
build_flag = "--pdf"   # EPUB and web-pdf share the --pdf run
```

### `7x10-color.toml`
```toml
extends = "edition"
format  = "7x10-color"
trim    = "7x10"
color   = true
build_flag = "--7x10"
isbn    = "979-8-9965852-2-9"
```

### `7x10-bw.toml`
```toml
extends = "edition"
format  = "7x10-bw"
trim    = "7x10"
color   = false
build_flag = "--7x10bw"
isbn    = "979-8-9965852-1-2"
```

### `8.5x11.toml`
```toml
extends = "edition"
format  = "8.5x11"
trim    = "8.5x11"
color   = true
build_flag = "--ingram"
isbn    = "979-8-9965852-3-6"
```

### `6x9.toml`
```toml
extends = "edition"
format  = "6x9"
trim    = "6x9"
color   = false
build_flag = "--6x9"
isbn    = "979-8-9965852-0-5"
```

---

## How `config.sh` resolves paths

`engine/lib/config.sh::load_config <edition> <format>`:

1. Reads `version` from `editions/<ed>/config/edition.toml` via Python `tomllib`.
2. Sets `BOOK_SOURCE_DIR = editions/<ed>/content`.
3. Sets `OUTPUT_DIR = editions/<ed>/output/<fmt>`.
4. Reads `build_flag` from `editions/<ed>/config/<fmt>.toml`; falls back to a hardcoded map if missing.
5. Sets `ARTIFACT_EXT` from format name (`epub` -> `epub`, `web-html` -> `html-dir`, everything else -> `pdf`).

The engine does not currently use `content_dir`, `output_base`, or `indexdata_dir` from `edition.toml`; paths are hardcoded conventions. Phase 2 will wire those keys.
