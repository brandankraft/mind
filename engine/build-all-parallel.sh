#!/usr/bin/env bash
#
# Build multiple book editions concurrently.
#
# Each target is run as its own `build-book.sh <target>` process. build-book.sh
# gives every invocation a private BOOK_TMP scratch dir (and build-book-pdf.py
# honors it), so the editions no longer clobber each other's intermediate files
# (/tmp/book-build.html, cover PDFs, pass2, crossref json, etc.).
#
# Usage:
#   ./scripts/build-all-parallel.sh --7x10 --6x9
#   ./scripts/build-all-parallel.sh --ingram --7x10 --6x9 --pdf
#   ./scripts/build-all-parallel.sh --web --epub        # (whatever build-book.sh accepts)
#
# Targets accepted by build-book.sh: --web --pdf --ingram --7x10 --6x9
#
# Caveat: each weasyprint run on the ~960-page book uses ~1-2 GB RAM and a core.
# Running 3-4 at once is fine on a 16 GB+/8-core Mac; more may swap.

set -u
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
unset BOOK_TMP   # so each child build-book.sh makes its OWN isolated temp dir

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <target> [target ...]   (e.g. --7x10 --6x9 --ingram)"
    exit 1
fi

pids=(); names=(); logs=()
for target in "$@"; do
    safe="${target#--}"; safe="${safe//\//_}"
    log="${TMPDIR:-/tmp}/buildlog-${safe}.log"
    : > "$log"
    echo "  launching ${target}  (log: ${log})"
    "$SCRIPT_DIR/build-book.sh" "$target" > "$log" 2>&1 &
    pids+=("$!"); names+=("$target"); logs+=("$log")
done

echo "  ${#pids[@]} editions building in parallel..."
echo
fail=0
for i in "${!pids[@]}"; do
    if wait "${pids[$i]}"; then
        last="$(grep -E 'pages|Done|done' "${logs[$i]}" | tail -1 | tr -d '\r')"
        echo "  [OK]   ${names[$i]}   ${last}"
    else
        echo "  [FAIL] ${names[$i]}   -- tail of ${logs[$i]}:"
        tail -3 "${logs[$i]}" | sed 's/^/        /'
        fail=1
    fi
done

echo
[ "$fail" -eq 0 ] && echo "  All builds completed." || echo "  One or more builds FAILED (see logs above)."
exit "$fail"
