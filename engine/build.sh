#!/usr/bin/env bash
# build.sh <edition> <format>
# Thin entrypoint for Mind2 book builds.
#
# Usage:
#   ./engine/build.sh 1st-edition web-html
#   ./engine/build.sh 1st-edition epub
#   ./engine/build.sh 1st-edition 7x10-color
#
# Formats: web-html  web-pdf  epub  7x10-color  7x10-bw  8.5x11  6x9

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$#" -lt 2 ]; then
  echo "Usage: $0 <edition> <format|all> [--parallel] [--chapter <file.md>]"
  echo "  Formats: web-html web-pdf epub 7x10-color 7x10-bw 8.5x11 6x9  (or 'all')"
  echo "  all [--parallel] : build every format (sequentially, or concurrently)"
  echo "  --chapter <file.md>: PDF formats only -- fast single-chapter/appendix render"
  echo "    for testing figure sizing/layout (folios + indexes are NOT faithful)."
  exit 1
fi

EDITION="$1"
FORMAT="$2"
shift 2

# Optional: render just one chapter/appendix for fast layout testing (PDF only).
# Passed to build-book-pdf.py via BOOK_CHAPTER_ONLY.
CHAPTER_ONLY=""
PARALLEL=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --chapter|--only) CHAPTER_ONLY="$2"; shift 2 ;;
    --parallel) PARALLEL=true; shift ;;
    *) echo "Unknown arg: $1"; exit 1 ;;
  esac
done

# ---- all-formats dispatcher -------------------------------------------------
# `all` builds every format. web-pdf + epub both come from one --pdf invocation,
# so we run 6 distinct builds (epub piggybacks on web-pdf) and then collect the
# epub artifact. --parallel runs the 6 concurrently (each writes its own
# output/<format>/ and a distinct content/ingramspark/<trim>.pdf, so they don't
# collide; each build-book.sh uses its own BOOK_TMP).
if [ "$FORMAT" = "all" ]; then
  PRIMARY="web-html web-pdf 7x10-color 7x10-bw 8.5x11 6x9"
  if [ "$PARALLEL" = true ]; then
    echo "== Building ALL formats in PARALLEL =="
    pids=""
    for f in $PRIMARY; do
      "$SCRIPT_DIR/build.sh" "$EDITION" "$f" & pids="$pids $!"
    done
    rc=0
    for p in $pids; do wait "$p" || rc=1; done
  else
    echo "== Building ALL formats sequentially =="
    rc=0
    for f in $PRIMARY; do
      "$SCRIPT_DIR/build.sh" "$EDITION" "$f" || rc=1
    done
  fi
  # epub piggybacks on the web-pdf (--pdf) build: collect it into output/epub/
  source "$SCRIPT_DIR/lib/config.sh"; load_config "$EDITION" "epub"
  mkdir -p "$OUTPUT_DIR"
  EPUB_SRC="$(dirname "$SCRIPT_DIR")/editions/$EDITION/output/web-pdf/downloads/a-thought-in-the-mind-of-god.epub"
  if [ -f "$EPUB_SRC" ]; then
    cp "$EPUB_SRC" "$OUTPUT_DIR/a-thought-in-the-mind-of-god-${VERSION}-epub.epub"
    echo "  Artifact (epub, from web-pdf build): $OUTPUT_DIR/a-thought-in-the-mind-of-god-${VERSION}-epub.epub"
  else
    echo "  WARN: epub not found at $EPUB_SRC"; rc=1
  fi
  echo "== ALL done (rc=$rc) =="
  exit $rc
fi
# ---------------------------------------------------------------------------
if [ -n "$CHAPTER_ONLY" ]; then
  case "$FORMAT" in
    web-html|epub) echo "Error: --chapter is supported for PDF formats only (not $FORMAT)."; exit 1 ;;
  esac
  export BOOK_CHAPTER_ONLY="$CHAPTER_ONLY"
  echo "  SINGLE-CHAPTER mode: $CHAPTER_ONLY (folios/indexes not faithful -- layout testing only)"
fi

# Load config (exports BOOK_SOURCE_DIR, OUTPUT_DIR, FORMAT_FLAG, ARTIFACT_EXT, VERSION)
# shellcheck source=engine/lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"
load_config "$EDITION" "$FORMAT"

mkdir -p "$OUTPUT_DIR"

SLUG="a-thought-in-the-mind-of-god"
INGRAMSPARK_DIR="$BOOK_SOURCE_DIR/ingramspark"
EDITION_DIR="$(dirname "$SCRIPT_DIR")/editions/$EDITION"
STATIC_CHAPTERS="$EDITION_DIR/static-chapters"

echo "Building edition=$EDITION format=$FORMAT flag=$FORMAT_FLAG"
echo "  BOOK_SOURCE_DIR=$BOOK_SOURCE_DIR"
echo "  OUTPUT_DIR=$OUTPUT_DIR"

if [ "$FORMAT" = "web-html" ]; then
  # Use a scratch directory so the build's chapters/ subdir + scratch files
  # are isolated; we then flatten the result into OUTPUT_DIR.
  SCRATCH_DIR="$(mktemp -d "${TMPDIR:-/tmp}/mind2-web-html.XXXXXX")"
  trap 'rm -rf "$SCRATCH_DIR"' EXIT

  # Pre-populate scratch/chapters with static HTML pages so build-book.sh
  # picks them up and includes them in chapters.json.
  mkdir -p "$SCRATCH_DIR/chapters"
  if [ -d "$STATIC_CHAPTERS" ]; then
    cp "$STATIC_CHAPTERS"/*.html "$SCRATCH_DIR/chapters/" 2>/dev/null || true
  fi

  FINAL_OUTPUT_DIR="$OUTPUT_DIR"
  export BOOK_SOURCE_DIR OUTPUT_DIR="$SCRATCH_DIR"
  "$SCRIPT_DIR/build-book.sh" --source "$BOOK_SOURCE_DIR" $FORMAT_FLAG

  # Flatten: copy chapters/*.html + chapters.json into the final OUTPUT_DIR.
  # This matches the golden layout (HTML at root, chapters.json at root).
  cp "$SCRATCH_DIR/chapters"/*.html "$FINAL_OUTPUT_DIR/"
  cp "$SCRATCH_DIR/chapters.json" "$FINAL_OUTPUT_DIR/chapters.json"
  OUTPUT_DIR="$FINAL_OUTPUT_DIR"
  echo "  Artifact: $OUTPUT_DIR/chapters.json (+ *.html)"
else
  # Non-web-html: invoke build-book.sh directly with the configured OUTPUT_DIR.
  export BOOK_SOURCE_DIR OUTPUT_DIR
  "$SCRIPT_DIR/build-book.sh" --source "$BOOK_SOURCE_DIR" $FORMAT_FLAG
fi

# Collect artifact into OUTPUT_DIR with versioned name
case "$FORMAT" in
  web-html)
    # Flattened output already in OUTPUT_DIR (handled above).
    ;;

  web-pdf)
    SRC="$OUTPUT_DIR/downloads/${SLUG}.pdf"
    DEST="$OUTPUT_DIR/${SLUG}-${VERSION}-web-pdf.pdf"
    [ -f "$SRC" ] && cp "$SRC" "$DEST" && echo "  Artifact: $DEST"
    ;;
  epub)
    SRC="$OUTPUT_DIR/downloads/${SLUG}.epub"
    DEST="$OUTPUT_DIR/${SLUG}-${VERSION}-epub.epub"
    [ -f "$SRC" ] && cp "$SRC" "$DEST" && echo "  Artifact: $DEST"
    ;;
  8.5x11)
    SRC="$INGRAMSPARK_DIR/${SLUG}-8.5x11-hardcover.pdf"
    DEST="$OUTPUT_DIR/${SLUG}-${VERSION}-8.5x11.pdf"
    [ -f "$SRC" ] && cp "$SRC" "$DEST" && echo "  Artifact: $DEST"
    ;;
  7x10-color)
    SRC="$INGRAMSPARK_DIR/${SLUG}-7x10.pdf"
    DEST="$OUTPUT_DIR/${SLUG}-${VERSION}-7x10-color.pdf"
    [ -f "$SRC" ] && cp "$SRC" "$DEST" && echo "  Artifact: $DEST"
    ;;
  7x10-bw)
    SRC="$INGRAMSPARK_DIR/${SLUG}-7x10-bw.pdf"
    DEST="$OUTPUT_DIR/${SLUG}-${VERSION}-7x10-bw.pdf"
    [ -f "$SRC" ] && cp "$SRC" "$DEST" && echo "  Artifact: $DEST"
    ;;
  6x9)
    SRC="$INGRAMSPARK_DIR/${SLUG}-6x9.pdf"
    DEST="$OUTPUT_DIR/${SLUG}-${VERSION}-6x9.pdf"
    [ -f "$SRC" ] && cp "$SRC" "$DEST" && echo "  Artifact: $DEST"
    ;;
esac

echo "Done: $EDITION/$FORMAT"
