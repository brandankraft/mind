#!/usr/bin/env bash
# config.sh -- load edition + format config for engine/build.sh
# Usage: source engine/lib/config.sh; load_config <edition> <format>
#
# After load_config, the following vars are exported:
#   BOOK_SOURCE_DIR   -- path to edition content/
#   OUTPUT_DIR        -- path to editions/<ed>/output/<fmt>/
#   FORMAT_FLAG       -- the flag to pass to build-book.sh (e.g. --web, --pdf, --7x10)
#   ARTIFACT_EXT      -- the primary artifact extension (html-dir | pdf | epub)
#   VERSION           -- book version string (from edition.toml)

load_config() {
  local ed="$1" fmt="$2"
  local root; root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
  local edir="$root/editions/$ed"
  local edition_toml="$edir/config/edition.toml"
  local format_toml="$edir/config/${fmt}.toml"

  # Read version from edition.toml
  VERSION=$(python3 -c "
import tomllib, sys
with open(sys.argv[1], 'rb') as f:
    d = tomllib.load(f)
print(d.get('version', '1.0'))
" "$edition_toml" 2>/dev/null || echo "1.0")

  export BOOK_SOURCE_DIR="$edir/content"
  export OUTPUT_DIR="$edir/output/$fmt"
  export VERSION

  # Map format -> build-book.sh flag (read from format TOML, fall back to hardcoded)
  local flag
  flag=$(python3 -c "
import tomllib, sys
with open(sys.argv[1], 'rb') as f:
    d = tomllib.load(f)
print(d.get('build_flag', ''))
" "$format_toml" 2>/dev/null) || flag=""

  if [ -z "$flag" ]; then
    # Hardcoded fallback (keeps identical mapping to the build brief)
    case "$fmt" in
      web-html)   flag="--web" ;;
      web-pdf)    flag="--pdf" ;;
      7x10-color) flag="--7x10" ;;
      7x10-bw)    flag="--7x10bw" ;;
      8.5x11)     flag="--ingram" ;;
      6x9)        flag="--6x9" ;;
      epub)       flag="--pdf" ;;
      *) echo "ERROR: unknown format '$fmt'" >&2; return 1 ;;
    esac
  fi
  export FORMAT_FLAG="$flag"

  case "$fmt" in
    web-html)          export ARTIFACT_EXT="html-dir" ;;
    epub)              export ARTIFACT_EXT="epub" ;;
    *)                 export ARTIFACT_EXT="pdf" ;;
  esac
}
