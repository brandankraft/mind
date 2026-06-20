# Adding an Edition

A second edition is a new subfolder under `editions/`. The engine is shared; you add content and config, not a new copy of the engine.

## Step 1: Create the edition directory

```bash
mkdir -p editions/2nd-edition/config
mkdir -p editions/2nd-edition/content
mkdir -p editions/2nd-edition/content/index-data
mkdir -p editions/2nd-edition/static-chapters
```

## Step 2: Copy or create `edition.toml`

```bash
cp editions/1st-edition/config/edition.toml editions/2nd-edition/config/edition.toml
```

Edit the copy:

```toml
title    = "A Thought in the Mind of God"
subtitle = "A Systematic Theology"
author   = "Brandan Kraft"
publisher = "Pristine Grace Publishing"
version  = "2.0"          # increment for the new edition

# Update ISBNs for the new edition
isbn_paperback_7x10      = "..."
isbn_hardcover_bw_7x10   = "..."
isbn_hardcover_color_7x10 = "..."
isbn_hardcover_color_8x11 = "..."
isbn_ebook               = "..."

content_dir   = "content"
output_base   = "output"
indexdata_dir = "content/index-data"

output_pattern = "{slug}-{version}-{format}"
slug = "a-thought-in-the-mind-of-god"
```

## Step 3: Copy the per-format TOML files

```bash
for f in web-html web-pdf epub 7x10-color 7x10-bw 8.5x11 6x9; do
    cp editions/1st-edition/config/${f}.toml editions/2nd-edition/config/${f}.toml
done
```

Update `isbn` values in the format files that carry per-format ISBNs. No other changes are needed for Phase-1 builds.

## Step 4: Populate `content/`

Copy or reorganize the source markdown, images, front-matter, covers, ingramspark directory, and index-data from the 1st edition (or start fresh for a genuine new edition).

```bash
# Starting from 1st edition as a baseline:
cp -r editions/1st-edition/content/. editions/2nd-edition/content/
```

Then make whatever content changes the new edition requires. The build picks up everything from `content/` by convention.

## Step 5: Copy `static-chapters/` if needed

```bash
cp -r editions/1st-edition/static-chapters/. editions/2nd-edition/static-chapters/
```

Static HTML chapters (cover, title-page, copyright, etc.) are pre-populated into the web-html scratch dir before the build runs. Update them for the new edition.

## Step 6: Build

```bash
engine/build.sh 2nd-edition web-html
engine/build.sh 2nd-edition web-pdf
engine/build.sh 2nd-edition epub
engine/build.sh 2nd-edition 7x10-color
# etc.
```

Output lands in `editions/2nd-edition/output/<format>/`.

## Step 7: Update index-data if needed

If the 2nd edition has significantly changed content, the precision index data (`topical-index.json`, `glossary-index.json`, figure placement JSONs) from the 1st edition will no longer be accurate. Run the relevant regeneration scripts:

```bash
# Rebuild the glossary index (after editing glossary content)
python3 engine/indexing/build_glossary_index.py editions/2nd-edition/content

# Rebuild the scripture index
python3 engine/indexing/build_scripture_index.py editions/2nd-edition/content
```

Topical index entries must be re-curated manually or with AI-assist if chapter text moves significantly.

## Step 8: `.gitignore`

The root `.gitignore` already covers `editions/*/output/` and `content/print-sized/`. No extra exclusions are needed for a new edition following the same layout.

---

## What the engine does and does not care about

**Does not care about:**
- The edition name (any folder name under `editions/` works)
- The version string (anything in `edition.toml::version`)
- The number of chapters or appendices (all markdown discovery is glob-based)

**Does care about:**
- `content/` having the expected file naming patterns (`chapter-NN-*.md`, `appendix-*.md`, `front-matter/`, `covers/`, `ingramspark/`)
- `content/index-data/` containing the JSON files the build reads (if present; all index-data reads are guarded with `os.path.exists()` checks)
- `static-chapters/` containing any static HTML pages that should appear in `chapters.json`
