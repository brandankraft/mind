#!/usr/bin/env bash
# normalize_epub.sh  <a.epub>  <b.epub>
#
# Exits 0 if the two EPUBs have identical content after stripping
# nondeterministic fields that pandoc/weasyprint vary run-to-run:
#   - dc:date        (build timestamp in content.opf)
#   - dcterms:modified  (build timestamp in content.opf)
#   - dc:identifier  (urn:uuid:... generated fresh by pandoc each build)
#   - dtb:uid meta   (mirrors the uuid in toc.ncx)
#   - ZIP entry mtimes (not extracted as file content; diff sees raw bytes)
#
# All other file content (text, HTML, CSS, images, structure) must match.

set -euo pipefail

A=$(mktemp -d)
B=$(mktemp -d)
trap 'rm -rf "$A" "$B"' EXIT

unzip -qq "$1" -d "$A"
unzip -qq "$2" -d "$B"

# Strip nondeterministic fields from content.opf in both trees.
# We use sed to remove or blank out the varying lines.
for dir in "$A" "$B"; do
    opf=$(find "$dir" -name "content.opf" | head -1)
    if [ -n "$opf" ]; then
        # Remove dc:date line entirely
        sed -i '' 's|<dc:date[^>]*>[^<]*</dc:date>||g' "$opf"
        # Remove dcterms:modified meta line entirely
        sed -i '' 's|<meta property="dcterms:modified">[^<]*</meta>||g' "$opf"
        # Blank out the UUID in dc:identifier (keep the tag structure, zero the value)
        sed -i '' 's|<dc:identifier id="epub-id-1">urn:uuid:[^<]*</dc:identifier>|<dc:identifier id="epub-id-1">urn:uuid:NORMALIZED</dc:identifier>|g' "$opf"
    fi
    # Also blank UUID in toc.ncx dtb:uid
    ncx=$(find "$dir" -name "toc.ncx" | head -1)
    if [ -n "$ncx" ]; then
        sed -i '' 's|<meta name="dtb:uid" content="urn:uuid:[^"]*"|<meta name="dtb:uid" content="urn:uuid:NORMALIZED"|g' "$ncx"
    fi
done

diff -r "$A" "$B"
