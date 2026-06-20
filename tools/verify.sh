#!/usr/bin/env bash
# verify.sh  <new_output_dir>  <golden_dir>
#
# Compares a fresh build output against the frozen golden baseline.
# Exits 0 iff every format matches after normalization.
# Prints a per-format PASS/FAIL table to stdout.
#
# Format layout (mirrored in both <new_output_dir> and <golden_dir>):
#   web-html/    -- directory of .html files (diff -r)
#   web-pdf/     -- *.pdf  (normalize_pdf.py + cmp)
#   7x10-color/  -- *.pdf
#   7x10-bw/     -- *.pdf
#   8.5x11/      -- *.pdf
#   6x9/         -- *.pdf
#   epub/        -- *.epub  (normalize_epub.sh)
#
# Usage:
#   bash ~/Anna/Mind2/tools/verify.sh <new_output_dir> <golden_dir>

set -uo pipefail

NEW="$1"
GOLD="$2"
TOOLS="$(cd "$(dirname "$0")" && pwd)"
fail=0

for fmt in web-html web-pdf 7x10-color 7x10-bw 8.5x11 6x9 epub; do
    new_path="$NEW/$fmt"
    gold_path="$GOLD/$fmt"

    # Existence check
    if [ ! -d "$new_path" ]; then
        echo "FAIL $fmt  (missing in new: $new_path)"
        fail=1
        continue
    fi
    if [ ! -d "$gold_path" ]; then
        echo "FAIL $fmt  (missing in golden: $gold_path)"
        fail=1
        continue
    fi

    case "$fmt" in
        web-html)
            if diff -rq "$new_path" "$gold_path" >/dev/null 2>&1; then
                echo "PASS $fmt"
            else
                echo "FAIL $fmt"
                diff -rq "$new_path" "$gold_path" | head -10
                fail=1
            fi
            ;;
        epub)
            new_epub=$(ls "$new_path"/*.epub 2>/dev/null | head -1)
            gold_epub=$(ls "$gold_path"/*.epub 2>/dev/null | head -1)
            if [ -z "$new_epub" ] || [ -z "$gold_epub" ]; then
                echo "FAIL $fmt  (no .epub found)"
                fail=1
            elif bash "$TOOLS/normalize_epub.sh" "$new_epub" "$gold_epub" >/dev/null 2>&1; then
                echo "PASS $fmt"
            else
                echo "FAIL $fmt"
                bash "$TOOLS/normalize_epub.sh" "$new_epub" "$gold_epub" 2>&1 | head -20
                fail=1
            fi
            ;;
        *)
            # PDF formats
            new_pdf=$(ls "$new_path"/*.pdf 2>/dev/null | head -1)
            gold_pdf=$(ls "$gold_path"/*.pdf 2>/dev/null | head -1)
            if [ -z "$new_pdf" ] || [ -z "$gold_pdf" ]; then
                echo "FAIL $fmt  (no .pdf found)"
                fail=1
                continue
            fi
            python3 "$TOOLS/normalize_pdf.py" "$new_pdf" /tmp/n_new.pdf 2>/dev/null
            python3 "$TOOLS/normalize_pdf.py" "$gold_pdf" /tmp/n_gold.pdf 2>/dev/null
            if cmp -s /tmp/n_new.pdf /tmp/n_gold.pdf; then
                echo "PASS $fmt"
            else
                echo "FAIL $fmt"
                fail=1
            fi
            ;;
    esac
done

echo ""
if [ "$fail" -eq 0 ]; then
    echo "ALL PASS"
else
    echo "SOME FORMATS FAILED"
fi
exit $fail
