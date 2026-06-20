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
  echo "Usage: $0 <edition> <format>"
  echo "  Formats: web-html web-pdf epub 7x10-color 7x10-bw 8.5x11 6x9"
  exit 1
fi

EDITION="$1"
FORMAT="$2"

# Load config (exports BOOK_SOURCE_DIR, OUTPUT_DIR, FORMAT_FLAG, ARTIFACT_EXT, VERSION)
# shellcheck source=engine/lib/config.sh
source "$SCRIPT_DIR/lib/config.sh"
load_config "$EDITION" "$FORMAT"

mkdir -p "$OUTPUT_DIR"

SLUG="a-thought-in-the-mind-of-god"
INGRAMSPARK_DIR="$BOOK_SOURCE_DIR/ingramspark"

echo "Building edition=$EDITION format=$FORMAT flag=$FORMAT_FLAG"
echo "  BOOK_SOURCE_DIR=$BOOK_SOURCE_DIR"
echo "  OUTPUT_DIR=$OUTPUT_DIR"

# Invoke the engine
export BOOK_SOURCE_DIR OUTPUT_DIR
"$SCRIPT_DIR/build-book.sh" $FORMAT_FLAG

# Collect artifact into OUTPUT_DIR with versioned name
case "$FORMAT" in
  web-html)
    # Already written to OUTPUT_DIR by build-book.sh (chapters/, chapters.json, etc.)
    echo "  Artifact: $OUTPUT_DIR/chapters.json (+ chapters/)"
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
