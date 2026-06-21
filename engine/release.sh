#!/usr/bin/env bash
# release.sh -- tag the current version and publish all built artifacts as a
# GitHub Release. This is the durable archive of every output version: the
# binaries live as release assets (outside git history, no clone bloat), tied
# to a version tag and the source commit they were built from.
#
# Run AFTER a clean build (engine/build.sh ... all) so every artifact exists.
#
# Usage: engine/release.sh [edition]        # default: 1st-edition
set -euo pipefail

ED="${1:-1st-edition}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EDIR="$ROOT/editions/$ED"
OUT="$EDIR/output"

VER=$(python3 -c "import tomllib,sys;print(tomllib.load(open(sys.argv[1],'rb'))['version'])" \
      "$EDIR/config/edition.toml")
TAG="v$VER"
HASH=$(git -C "$ROOT" rev-parse --short HEAD)

# Collect this version's artifacts (5 PDFs + EPUB + the provenance file).
ASSETS=""
for f in "$OUT"/*/a-thought-in-the-mind-of-god-"$VER"-*.pdf \
         "$OUT"/epub/a-thought-in-the-mind-of-god-"$VER"-epub.epub \
         "$EDIR/VERSION.txt"; do
  [ -f "$f" ] && ASSETS="$ASSETS $f"
done

if [ -z "$ASSETS" ]; then
  echo "ERROR: no artifacts found for version $VER. Build first:" >&2
  echo "  ./engine/build.sh $ED all --parallel" >&2
  exit 1
fi

echo "Releasing $TAG (build $HASH)"
echo "Assets:"; for a in $ASSETS; do echo "  $(basename "$a")"; done

# Tag (idempotent: skip if it already exists) and push.
if ! git -C "$ROOT" rev-parse "$TAG" >/dev/null 2>&1; then
  git -C "$ROOT" tag -a "$TAG" -m "A Thought in the Mind of God -- Version $VER"
  git -C "$ROOT" push origin "$TAG"
fi

# Create the release if absent, else upload/replace assets onto the existing one.
if gh release view "$TAG" >/dev/null 2>&1; then
  echo "Release $TAG exists -- uploading/clobbering assets."
  # shellcheck disable=SC2086
  gh release upload "$TAG" $ASSETS --clobber
else
  # shellcheck disable=SC2086
  gh release create "$TAG" $ASSETS \
    --title "$TAG" \
    --notes "Version $VER · build $HASH. Artifacts: all print/web PDFs + EPUB + VERSION.txt."
fi

echo "Done: $(gh release view "$TAG" --json url -q .url)"
