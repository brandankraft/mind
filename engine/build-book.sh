#!/bin/bash
# =============================================================================
# Build & Deploy "A Thought in the Mind of God"
#
# Builds HTML chapters, EPUB, Web PDF, and/or IngramSpark interior PDFs.
# Deploys HTML + web downloads to Joshua (pristinegrace.org).
#
# Usage:
#   ./scripts/build-book.sh --web        # HTML chapters + deploy
#   ./scripts/build-book.sh --pdf        # EPUB + Web PDF (for PG downloads) + deploy
#   ./scripts/build-book.sh --ingram     # IngramSpark 8.5x11 interior (local only, no deploy)
#   ./scripts/build-book.sh --6x9        # 6x9 B&W paperback interior, 10.5pt (local only, no deploy)
#   ./scripts/build-book.sh --7x10       # 7x10 textbook interior, 11pt, color-capable (local only, no deploy)
#   ./scripts/build-book.sh --all        # web + pdf + ingram (not 6x9)
#   ./scripts/build-book.sh --web --pdf  # Modes compose
#   ./scripts/build-book.sh              # Defaults to --all (back-compat)
#
# Additional flags:
#   --source DIR    Override source directory
#   --help, -h      Show this help
#
# Publish via git: this script only builds locally. Run ./scripts/deploy.sh
# afterwards to commit + push + pull on Joshua.
#
# Configuration:
#   Create .book-build.conf in project root with:
#     BOOK_SOURCE_DIR="/path/to/Mind/"
#
# Requirements: pandoc, weasyprint, pypdf, ssh access to joshua
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
# Per-invocation scratch dir (exported so build-book-pdf.py children share it).
# Each separate run of this script gets its own, so multiple editions can build
# in parallel without their /tmp scratch files colliding. Cleaned up on exit.
export BOOK_TMP="${BOOK_TMP:-$(mktemp -d "${TMPDIR:-/tmp}/bookbuild.XXXXXX")}"
trap '[ -n "$BOOK_TMP" ] && [ -d "$BOOK_TMP" ] && rm -rf "$BOOK_TMP"' EXIT
OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_DIR/public_html/book-content}"
CONF_FILE="$PROJECT_DIR/.book-build.conf"
REMOTE_HOST="joshua"
REMOTE_PATH="/home/pristinegrace/public_html/book-content"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Defaults
BOOK_SOURCE_DIR=""
BUILD_WEB=false
BUILD_PDF=false
BUILD_EPUB=false
BUILD_INGRAM=false
BUILD_6X9=false
BUILD_7X10=false
BUILD_7X10BW=false
BUILD=true
HTML_COUNT=0

# =============================================================================
# ARG PARSING
# =============================================================================
while [[ $# -gt 0 ]]; do
    case "$1" in
        --web)
            BUILD_WEB=true
            shift
            ;;
        --pdf)
            BUILD_PDF=true
            shift
            ;;
        --epub)
            BUILD_EPUB=true
            shift
            ;;
        --ingram)
            BUILD_INGRAM=true
            shift
            ;;
        --7x10)
            BUILD_7X10=true
            BUILD=true
            shift
            ;;
        --7x10bw)
            BUILD_7X10BW=true
            BUILD=true
            shift
            ;;
        --6x9)
            BUILD_6X9=true
            shift
            ;;
        --all)
            BUILD_WEB=true
            BUILD_PDF=true
            BUILD_INGRAM=true
            shift
            ;;
        --source)
            BOOK_SOURCE_DIR="$2"
            shift 2
            ;;
        --help|-h)
            sed -n '3,26p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Run with --help for usage."
            exit 1
            ;;
    esac
done

# If no mode flag given, default to all (preserves original behavior)
if [ "$BUILD_WEB" = false ] && [ "$BUILD_PDF" = false ] && [ "$BUILD_EPUB" = false ] && [ "$BUILD_INGRAM" = false ] && [ "$BUILD_6X9" = false ] && [ "$BUILD_7X10" = false ] && [ "$BUILD_7X10BW" = false ]; then
    BUILD_WEB=true
    BUILD_PDF=true
    BUILD_INGRAM=true
fi

# Load config if no --source given
if [ -z "$BOOK_SOURCE_DIR" ] && [ -f "$CONF_FILE" ]; then
    source "$CONF_FILE"
fi
BOOK_SOURCE_DIR="${BOOK_SOURCE_DIR/#\~/$HOME}"

# Validate source directory (only required when building)
if [ "$BUILD" = true ]; then
    if [ -z "$BOOK_SOURCE_DIR" ]; then
        echo -e "${RED}Error: No source directory configured.${NC}"
        echo ""
        echo "Either:"
        echo "  1. Create $CONF_FILE with: BOOK_SOURCE_DIR=\"/path/to/book/\""
        echo "  2. Pass --source /path/to/book/"
        exit 1
    fi
    if [ ! -d "$BOOK_SOURCE_DIR" ]; then
        echo -e "${RED}Error: Source directory not found: $BOOK_SOURCE_DIR${NC}"
        exit 1
    fi
    if ! command -v pandoc &> /dev/null; then
        echo -e "${RED}Error: pandoc is required but not installed.${NC}"
        echo "  brew install pandoc"
        exit 1
    fi
fi

echo ""
echo -e "${BLUE}Building \"A Thought in the Mind of God\"...${NC}"
[ "$BUILD" = true ] && echo -e "  Source: ${YELLOW}$BOOK_SOURCE_DIR${NC}"
MODES=()
[ "$BUILD_WEB" = true ]    && MODES+=("web")
[ "$BUILD_PDF" = true ]    && MODES+=("pdf")
[ "$BUILD_EPUB" = true ]   && MODES+=("epub")
[ "$BUILD_INGRAM" = true ] && MODES+=("ingram")
[ "$BUILD_6X9" = true ]    && MODES+=("6x9")
[ "$BUILD_7X10" = true ]   && MODES+=("7x10")
[ "$BUILD_7X10BW" = true ] && MODES+=("7x10bw")
echo -e "  Modes:  ${YELLOW}${MODES[*]}${NC}"
echo ""

# =============================================================================
# SHARED HELPERS
# =============================================================================

# Strip YAML frontmatter from a markdown file
strip_frontmatter() {
    local input="$1"
    if head -1 "$input" | grep -q '^---$'; then
        awk 'BEGIN{skip=0; found=0} /^---$/{if(found==0){found=1;skip=1;next}else if(skip==1){skip=0;next}} skip==0{print}' "$input"
    else
        cat "$input"
    fi
}

# Extract first H1 title from markdown
extract_title() {
    local input="$1"
    strip_frontmatter "$input" | grep -m1 '^# ' | sed 's/^# //'
}

# =============================================================================
# MODE: WEB  —  HTML chapters + covers + post-build transforms
# =============================================================================
if [ "$BUILD" = true ] && [ "$BUILD_WEB" = true ]; then
    echo -e "${BLUE}▸ Web HTML${NC}"

    # Create output directories
    mkdir -p "$OUTPUT_DIR/chapters"
    mkdir -p "$OUTPUT_DIR/downloads"
    mkdir -p "$OUTPUT_DIR/covers"

    # Count what we have
    CHAPTER_COUNT=0
    APPENDIX_COUNT=0
    HAS_PROLOGUE=false
    HAS_PREFACE=false
    HAS_EPILOGUE=false

    [ -f "$BOOK_SOURCE_DIR/prologue.md" ] && HAS_PROLOGUE=true
    [ -f "$BOOK_SOURCE_DIR/preface.md" ] && HAS_PREFACE=true
    [ -f "$BOOK_SOURCE_DIR/epilogue.md" ] && HAS_EPILOGUE=true

    for f in "$BOOK_SOURCE_DIR"/chapter-*.md; do
        [ -f "$f" ] && CHAPTER_COUNT=$((CHAPTER_COUNT + 1))
    done

    for f in "$BOOK_SOURCE_DIR"/appendix-*.md; do
        [ -f "$f" ] && APPENDIX_COUNT=$((APPENDIX_COUNT + 1))
    done

    echo -e "  Found ${GREEN}$CHAPTER_COUNT chapters${NC}, ${GREEN}$APPENDIX_COUNT appendices${NC}, prologue, preface, epilogue"

    # Part mapping (chapter number -> part name)
    get_part() {
        local num=$1
        if [ "$num" -le 5 ]; then echo "Part I: The Foundation"
        elif [ "$num" -le 6 ]; then echo "Part II: The Person"
        elif [ "$num" -le 10 ]; then echo "Part III: The Covenant"
        elif [ "$num" -le 14 ]; then echo "Part IV: The People"
        elif [ "$num" -le 19 ]; then echo "Part V: Salvation"
        elif [ "$num" -le 24 ]; then echo "Part VI: The Life"
        elif [ "$num" -le 26 ]; then echo "Part VII: Knowing"
        elif [ "$num" -le 29 ]; then echo "Part VIII: The End"
        else echo "Part IX: The Landing"
        fi
    }

    # Start building chapters.json
    JSON='{\n  "title": "A Thought in the Mind of God",\n  "subtitle": "A Systematic Theology",\n  "author": "Brandan Kraft",\n  "chapters": ['

    FIRST=true

    # Helper to add a chapter entry to JSON and convert to HTML
    process_chapter() {
        local slug="$1"
        local title="$2"
        local part="$3"
        local file="$4"
        local source_md="$5"

        # Convert markdown to HTML fragment
        strip_frontmatter "$source_md" | pandoc --from markdown+smart --to html5 --syntax-highlighting=none -o "$OUTPUT_DIR/chapters/$file"
        # Convert en dashes to em dashes
        sed -i '' 's/–/—/g' "$OUTPUT_DIR/chapters/$file"
        # Inject cross-reference links (Related Appendices / Referenced in Chapters)
        python3 -c "
import sys, re, json
sys.path.insert(0, '$SCRIPT_DIR/lib')

slug = '$slug'
html_path = '$OUTPUT_DIR/chapters/$file'

with open('${BOOK_TMP}/book-crossref.json') as f:
    xref = json.load(f)

with open(html_path) as f:
    html = f.read()

changed = False

# For chapters: inject Related Appendices after For Further Study heading
ch_match = re.match(r'^(\d+)$', slug)
if ch_match:
    ch_num = ch_match.group(1)
    if ch_num in xref.get('ch', {}):
        entries = xref['ch'][ch_num]
        lines = ['<div class=\"related-appendices\">', '<h3 id=\"related-appendices\">Related Appendices</h3>']
        for key, title, hslug, subs in entries:
            short = title.split(': ', 1)[1] if ': ' in title else title
            app_slug = f'appendix-{key.lower()}'
            if subs:
                lines.append(f'<p><strong><a href=\"/mind/chapter/{app_slug}\">Appendix {key}: {short}</a></strong></p>')
                lines.append('<ul>')
                for sub_title, sub_slug in subs:
                    lines.append(f'<li><a href=\"/mind/chapter/{app_slug}#{sub_slug}\">{sub_title}</a></li>')
                lines.append('</ul>')
            else:
                lines.append(f'<p><a href=\"/mind/chapter/{app_slug}\">Appendix {key}: {short}</a></p>')
        lines.append('</div>')
        block = '\n'.join(lines)
        # Insert before closing of the document (at the end)
        html = html.rstrip() + '\n' + block + '\n'
        changed = True

if changed:
    with open(html_path, 'w') as f:
        f.write(html)
" 2>/dev/null
        HTML_COUNT=$((HTML_COUNT + 1))

        # Add to JSON
        if [ "$FIRST" = true ]; then
            FIRST=false
        else
            JSON="$JSON,"
        fi

        local part_json="null"
        if [ -n "$part" ]; then
            part_json="\"$part\""
        fi

        # Escape any quotes in title
        local escaped_title=$(echo "$title" | sed 's/"/\\"/g')

        # Extract ## and ### section headings from source markdown
        # ### headings become sub-sections (indented in sidebar/modal)
        local sections_json="[]"
        if [ -f "$source_md" ]; then
            sections_json=$(python3 -c "
import re, json, sys
with open(sys.argv[1]) as f:
    lines = f.readlines()
has_h3 = any(line.startswith('### ') for line in lines)
sections = []
for line in lines:
    if line.startswith('## ') and not line.startswith('### '):
        # Only include ## headings as sections if there are no ### headings
        # When ### exists, ## becomes group labels (rendered separately by section_groups)
        if not has_h3:
            sections.append(line[3:].strip())
        else:
            sections.append('~group~' + line[3:].strip())
    elif has_h3 and line.startswith('### '):
        sections.append('~sub~' + line[4:].strip())
if not sections:
    print('[]')
else:
    print(json.dumps(sections))
" "$source_md")
        fi

        JSON="$JSON\n    { \"slug\": \"$slug\", \"title\": \"$escaped_title\", \"part\": $part_json, \"file\": \"$file\", \"sections\": $sections_json }"
    }

    echo -n "  Converting chapters to HTML..."

    # Generate cross-reference map (chapter <-> appendix links)
    CROSSREF_JSON=$(python3 -c "
import sys; sys.path.insert(0, '$SCRIPT_DIR/lib')
from crossrefs import build_crossref_map
import json
ch_map, app_map = build_crossref_map('$BOOK_SOURCE_DIR')
print(json.dumps({'ch': {str(k): v for k, v in ch_map.items()}, 'app': app_map}))
" 2>/dev/null)
    echo "$CROSSREF_JSON" > ${BOOK_TMP}/book-crossref.json

    # Front matter pages (static HTML, not from markdown source)
    # These are maintained in public_html/book-content/chapters/ and persist across builds
    # Front matter pages at the beginning
    for fm_entry in "cover:Cover" "title-page:Title Page" "about:About This Book" "copyright:Copyright" "dedication:Dedication"; do
        fm_slug="${fm_entry%%:*}"
        fm_title="${fm_entry#*:}"
        fm_file="$OUTPUT_DIR/chapters/${fm_slug}.html"
        if [ -f "$fm_file" ]; then
            if [ "$FIRST" = true ]; then FIRST=false; else JSON="$JSON,"; fi
            JSON="$JSON\n    { \"slug\": \"$fm_slug\", \"title\": \"$fm_title\", \"part\": null, \"file\": \"${fm_slug}.html\", \"sections\": [] }"
        fi
    done

    # Voiced front matter order: Foreword (Higby's outside voice) -> Preface (the
    # author's) -> Acknowledgments -> Prologue -> How This Book Talks -> chapters.
    FWDFILE="$BOOK_SOURCE_DIR/front-matter/foreword.md"
    if [ -f "$FWDFILE" ]; then
        process_chapter "foreword" "Foreword" "" "foreword.html" "$FWDFILE"
    fi

    # Preface
    if [ "$HAS_PREFACE" = true ]; then
        TITLE=$(extract_title "$BOOK_SOURCE_DIR/preface.md")
        [ -z "$TITLE" ] && TITLE="Preface"
        process_chapter "preface" "$TITLE" "" "preface.html" "$BOOK_SOURCE_DIR/preface.md"
    fi

    # Acknowledgments (after the Preface)
    ACKFILE="$BOOK_SOURCE_DIR/front-matter/06-acknowledgments.md"
    if [ -f "$ACKFILE" ]; then
        process_chapter "acknowledgments" "Acknowledgments" "" "acknowledgments.html" "$ACKFILE"
    fi

    # Prologue
    if [ "$HAS_PROLOGUE" = true ]; then
        TITLE=$(extract_title "$BOOK_SOURCE_DIR/prologue.md")
        [ -z "$TITLE" ] && TITLE="Prologue"
        process_chapter "prologue" "$TITLE" "" "prologue.html" "$BOOK_SOURCE_DIR/prologue.md"
    fi

    # How This Book Talks
    HTBTFILE="$BOOK_SOURCE_DIR/how-this-book-talks.md"
    if [ -f "$HTBTFILE" ]; then
        process_chapter "how-this-book-talks" "How This Book Talks" "" "how-this-book-talks.html" "$HTBTFILE"
    fi

    # Chapters 1-30
    for i in $(seq 1 30); do
        PADDED=$(printf "%02d" "$i")
        CHAPFILE=$(ls "$BOOK_SOURCE_DIR"/chapter-${PADDED}-*.md 2>/dev/null | head -1)
        if [ -z "$CHAPFILE" ]; then
            # Try without padding
            CHAPFILE=$(ls "$BOOK_SOURCE_DIR"/chapter-${i}-*.md 2>/dev/null | head -1)
        fi
        if [ -n "$CHAPFILE" ] && [ -f "$CHAPFILE" ]; then
            TITLE=$(extract_title "$CHAPFILE")
            [ -z "$TITLE" ] && TITLE="Chapter $i"
            # Strip "Chapter N: " or "Chapter N - " prefix from title if present
            TITLE=$(echo "$TITLE" | sed -E 's/^Chapter [0-9]+[: -]+ *//')
            PART=$(get_part "$i")
            process_chapter "$i" "$TITLE" "$PART" "chapter-${PADDED}.html" "$CHAPFILE"
        fi
    done

    # Epilogue
    if [ "$HAS_EPILOGUE" = true ]; then
        TITLE=$(extract_title "$BOOK_SOURCE_DIR/epilogue.md")
        [ -z "$TITLE" ] && TITLE="Epilogue"
        process_chapter "epilogue" "$TITLE" "" "epilogue.html" "$BOOK_SOURCE_DIR/epilogue.md"
    fi

    # Afterword (after the epilogue, before the appendices)
    AFTERWORD_FILE="$BOOK_SOURCE_DIR/afterword.md"
    if [ -f "$AFTERWORD_FILE" ]; then
        TITLE=$(extract_title "$AFTERWORD_FILE")
        [ -z "$TITLE" ] && TITLE="Afterword"
        process_chapter "afterword" "$TITLE" "" "afterword.html" "$AFTERWORD_FILE"
    fi

    # Appendices. Applied appendices A1-A12 come first (in numeric order), then
    # single-letter appendices B-Q. Each becomes its own chapter entry with the
    # key as the slug (e.g. `appendix-a1`, `appendix-a2`, ..., `appendix-b`).
    # Build the ordered list of keys by scanning the source directory.
    APP_KEYS=""
    for n in 1 2 3 4 5 6 7 8 9 10 11 12; do
        if ls "$BOOK_SOURCE_DIR"/appendix-a${n}-*.md 2>/dev/null | head -1 | grep -q .; then
            APP_KEYS="$APP_KEYS a${n}"
        fi
    done
    for letter in b c d e f g h i j k l m n o r s p q; do
        APP_KEYS="$APP_KEYS $letter"
    done

    for key in $APP_KEYS; do
        APPFILE=$(ls "$BOOK_SOURCE_DIR"/appendix-${key}-*.md 2>/dev/null | head -1)
        if [ -z "$APPFILE" ]; then
            APPFILE=$(ls "$BOOK_SOURCE_DIR"/appendix-${key}.md 2>/dev/null | head -1)
        fi
        if [ -n "$APPFILE" ] && [ -f "$APPFILE" ]; then
            TITLE=$(extract_title "$APPFILE")
            KEY_UPPER=$(echo "$key" | tr 'a-z' 'A-Z')
            [ -z "$TITLE" ] && TITLE="Appendix ${KEY_UPPER}"
            # Strip "Appendix X[N]: " prefix if present
            TITLE=$(echo "$TITLE" | sed -E 's/^Appendix [A-Z][0-9]*[: -]+ *//')
            process_chapter "appendix-${key}" "$TITLE" "Appendices" "appendix-${key}.html" "$APPFILE"
        fi
    done

    # About the Author (final content page, after the appendices/indexes).
    ABOUT_FILE="$BOOK_SOURCE_DIR/about-the-author.md"
    if [ -f "$ABOUT_FILE" ]; then
        ABOUT_TITLE=$(extract_title "$ABOUT_FILE")
        [ -z "$ABOUT_TITLE" ] && ABOUT_TITLE="About the Author"
        process_chapter "about-the-author" "$ABOUT_TITLE" "" "about-the-author.html" "$ABOUT_FILE"
    fi

    # Grace and Peace (Eileen Beckett memorial) -- the book's literal last page.
    GRACE_FILE="$BOOK_SOURCE_DIR/grace-and-peace.md"
    if [ -f "$GRACE_FILE" ]; then
        process_chapter "grace-and-peace" "Grace and Peace" "" "grace-and-peace.html" "$GRACE_FILE"
    fi

    # Back cover (static HTML, at the end)
    bc_file="$OUTPUT_DIR/chapters/back-cover.html"
    if [ -f "$bc_file" ]; then
        JSON="$JSON,\n    { \"slug\": \"back-cover\", \"title\": \"Back Cover\", \"part\": null, \"file\": \"back-cover.html\", \"sections\": [] }"
    fi

    JSON="$JSON\n  ]\n}"

    echo -e " ${GREEN}done${NC} ($HTML_COUNT files)"

    # Write chapters.json and convert dashes to em dashes in titles
    echo -e "$JSON" | sed 's/ -- / — /g' > "$OUTPUT_DIR/chapters.json"

    # Build topical heading map: for each chapter, extract heading IDs, text, and positions
    # so the topical index can link directly to relevant sections (by heading title or body content)
    echo -ne "  Linking index references..."
    HEADING_MAP="$BOOK_SOURCE_DIR/.scripture-heading-map.json"
    python3 -c "
import re, json, os, glob, sys

output_dir = sys.argv[1]
chapters_dir = os.path.join(output_dir, 'chapters')
topical_map = {}   # {chapter_slug: {heading_id: heading_text}}
chapter_html = {}  # {chapter_slug: full_html} -- for body-text search fallback
heading_order = {} # {chapter_slug: [(pos, heading_id), ...]} -- ordered by position

for html_file in sorted(glob.glob(os.path.join(chapters_dir, '*.html'))):
    slug = os.path.splitext(os.path.basename(html_file))[0]
    if slug.startswith('chapter-'):
        ch_num = slug.replace('chapter-', '').lstrip('0') or '0'
        map_key = ch_num
    else:
        map_key = slug

    with open(html_file) as f:
        content = f.read()

    chapter_html[map_key] = content
    headings = {}
    positions = []
    for m in re.finditer(r'<h[23][^>]*id=\"([^\"]+)\"[^>]*>(.*?)</h[23]>', content, re.DOTALL):
        hid = m.group(1)
        htext = re.sub(r'<[^>]+>', '', m.group(2)).strip().lower()
        headings[hid] = htext
        positions.append((m.start(), hid))

    if headings:
        topical_map[map_key] = headings
        heading_order[map_key] = positions

data = {'headings': topical_map, 'html': chapter_html, 'order': heading_order}
with open(os.path.join(output_dir, '.topical-heading-map.json'), 'w') as f:
    json.dump(data, f)
" "$OUTPUT_DIR"

    # Appendix P (Scripture index) still uses the legacy heading-based linker.
    # Appendix Q (Topical index) is rebuilt later by inject_web_index.py from the
    # paragraph-precise index-data (same source the PDF/EPUB use), so it's omitted here.
    for idx_file in "$OUTPUT_DIR/chapters/appendix-p.html"; do
        if [ -f "$idx_file" ]; then
            python3 -c "
import re, sys, json, os

idx_file = sys.argv[1]
map_file = sys.argv[2]
topical_map_file = sys.argv[3]
is_scripture = 'appendix-p' in idx_file
is_topical = 'appendix-q' in idx_file

with open(idx_file, 'r') as f:
    html = f.read()

# Load heading maps
heading_map = {}
if os.path.exists(map_file):
    with open(map_file) as f:
        heading_map = json.load(f)

topical_data = {}
if os.path.exists(topical_map_file):
    with open(topical_map_file) as f:
        topical_data = json.load(f)

topical_map = topical_data.get('headings', {})
chapter_html_map = topical_data.get('html', {})
heading_order_map = topical_data.get('order', {})

def find_heading_for_ref(chapter_slug, scripture_ref):
    \"\"\"Find which heading in a chapter contains a given scripture reference.
    Strategy 1: Use the pre-built scripture heading map.
    Strategy 2: Search chapter body text for the scripture reference.\"\"\"
    slug = str(chapter_slug)
    # Strategy 1: scripture heading map
    ch_data = heading_map.get(slug, {})
    for heading_id, refs in ch_data.items():
        for ref in refs:
            if scripture_ref and scripture_ref.lower() in ref.lower():
                return heading_id

    # Strategy 2: body text search for the scripture reference
    if not scripture_ref:
        return None
    ch_html = chapter_html_map.get(slug, '')
    ch_order = heading_order_map.get(slug, [])
    if not ch_html or not ch_order:
        return None

    # Search for the book name (first word(s)) in the chapter HTML
    # e.g. 'Genesis 1:1' -> search for 'Genesis 1:1', then 'Genesis 1', then 'Genesis'
    ref_clean = scripture_ref.strip()
    search_terms = [ref_clean]
    # Also try just book + chapter (e.g. 'Genesis 1')
    colon_pos = ref_clean.find(':')
    if colon_pos > 0:
        search_terms.append(ref_clean[:colon_pos])

    for term in search_terms:
        pattern = re.escape(term)
        match = re.search(pattern, ch_html, re.IGNORECASE)
        if match:
            pos = match.start()
            best_heading = None
            for hpos, hid in ch_order:
                if hid == 'for-further-study':
                    continue
                if hpos <= pos:
                    best_heading = hid
                else:
                    break
            if best_heading:
                return best_heading

    return None

def find_heading_for_topic(chapter_slug, topic_keywords):
    \"\"\"Find the best heading in a chapter that matches topic keywords.
    Strategy 1: Match keywords against heading titles.
    Strategy 2: Search body text for keywords, find nearest preceding heading.\"\"\"
    slug = str(chapter_slug)
    ch_headings = topical_map.get(slug, {})
    topic_lower = topic_keywords.lower()

    stop_words = {'the','a','an','of','in','as','is','and','or','not','vs','for','to','by','on','at','its','but','no','all','from','that','with','into','this','than'}
    words = [w for w in re.findall(r'[a-z]+', topic_lower) if len(w) > 2 and w not in stop_words]
    if not words:
        return None

    # Strategy 1: heading title match
    best_id = None
    best_score = 0
    for heading_id, heading_text in ch_headings.items():
        if heading_id == 'for-further-study':
            continue
        score = sum(1 for w in words if w in heading_text)
        if score > best_score:
            best_score = score
            best_id = heading_id
    if best_score >= 1:
        return best_id

    # Strategy 2: body text search -- find keyword in chapter HTML, return nearest heading above it
    ch_html = chapter_html_map.get(slug, '')
    ch_order = heading_order_map.get(slug, [])
    if not ch_html or not ch_order:
        return None

    # Search for the longest keyword first (more specific match)
    words_sorted = sorted(words, key=len, reverse=True)
    for word in words_sorted:
        # Case-insensitive search in body text (skip matches inside HTML tags)
        pattern = rf'(?<![a-zA-Z]){re.escape(word)}(?![a-zA-Z])'
        match = re.search(pattern, ch_html, re.IGNORECASE)
        if match:
            pos = match.start()
            # Find the nearest heading that precedes this position
            best_heading = None
            for hpos, hid in ch_order:
                if hid == 'for-further-study':
                    continue
                if hpos <= pos:
                    best_heading = hid
                else:
                    break
            if best_heading:
                return best_heading

    return None

def extract_scripture_from_context(html_context):
    \"\"\"Try to extract the scripture reference from nearby HTML text.\"\"\"
    m = re.search(r'<strong>([^<]+)</strong>', html_context)
    if m:
        return m.group(1).strip()
    return None

# Normalize pandoc line-wrapping: collapse newlines between tags so refs like 'Ch.\n20' become 'Ch. 20'
html = re.sub(r'(?<=\S)\n(?=\S)', ' ', html)

# Extract topic/scripture name per list item for heading anchoring
# Build a map of position -> keywords from <strong> tags in each <li>
entry_at_pos = {}
for m in re.finditer(r'<strong>([^<]+)</strong>', html):
    raw = m.group(1).strip()
    clean = re.sub(r'\([^)]*\)', '', raw).strip()
    entry_at_pos[m.start()] = clean

def get_entry_for_pos(pos):
    \"\"\"Find the nearest entry keyword that precedes this position.\"\"\"
    best_pos = -1
    for tp in entry_at_pos:
        if tp <= pos and tp > best_pos:
            best_pos = tp
    return entry_at_pos.get(best_pos, '')

# Replace 'Ch. N' with link to chapter (with heading anchor for topical/scripture index)
def extract_trailing_hint(m):
    rest = html[m.end():m.end()+200]
    mm = re.match(r'\s*\(([^)]+)\)', rest)
    return mm.group(1).strip() if mm else None

def ch_link(m):
    n = m.group(1)
    anchor = ''
    hint = extract_trailing_hint(m)
    entry = get_entry_for_pos(m.start())
    heading = None
    if is_topical:
        if hint:
            heading = find_heading_for_topic(n, hint)
        if not heading and entry:
            heading = find_heading_for_topic(n, entry)
    elif is_scripture and entry:
        heading = find_heading_for_ref(n, entry)
    if heading:
        anchor = f'#{heading}'
    href = f'/mind/chapter/{n}{anchor}'
    return f'<a href=\"{href}\" class=\"idx-link\">Ch. {n}</a>'

html = re.sub(r'(?<![a-zA-Z])Ch\.\s+(\d+)(?!\d)', ch_link, html)

# Replace 'Ch. N (FS)' pattern
html = re.sub(r'(?<![a-zA-Z])(\d+)\s+\(FS\)', lambda m: f'<a href=\"/mind/chapter/{m.group(1)}#for-further-study\" class=\"idx-link\">{m.group(1)} (FS)</a>', html)

# Replace 'App. X' / 'App. A1'-'App. A12' with link to appendix (with heading anchor for both indexes)
# Applied appendices are A1-A12; single-letter B-S (B-N theological, O = Floor, P-S reference back-matter).
app_map = {'A1':'a1','A2':'a2','A3':'a3','A4':'a4','A5':'a5','A6':'a6','A7':'a7','A8':'a8','A9':'a9','A10':'a10','A11':'a11','A12':'a12','B':'b','C':'c','D':'d','E':'e','F':'f','G':'g','H':'h','I':'i','J':'j','K':'k','L':'l','M':'m','N':'n','O':'o','P':'p','Q':'q','R':'r','S':'s'}
def app_link(letter_upper, letter_lower, m):
    slug = f'appendix-{letter_lower}'
    anchor = ''
    hint = extract_trailing_hint(m)
    entry = get_entry_for_pos(m.start())
    heading = None
    if is_topical:
        if hint:
            heading = find_heading_for_topic(slug, hint)
        if not heading and entry:
            heading = find_heading_for_topic(slug, entry)
    elif is_scripture and entry:
        heading = find_heading_for_ref(slug, entry)
    if heading:
        anchor = f'#{heading}'
    return f'<a href=\"/mind/chapter/{slug}{anchor}\" class=\"idx-link\">App. {letter_upper}</a>'

# Sort by descending length so 'A12' matches before 'A1' before (never) 'A' alone.
for letter_upper in sorted(app_map.keys(), key=lambda s: -len(s)):
    letter_lower = app_map[letter_upper]
    html = re.sub(rf'App\.\s+{letter_upper}(?![a-z0-9])', lambda m, lu=letter_upper, ll=letter_lower: app_link(lu, ll, m), html)

# Replace 'Prologue' 'Preface' 'Epilogue' references
for name in ['Prologue', 'Preface', 'Epilogue']:
    slug = name.lower()
    if is_topical or is_scripture:
        def special_link(m, s=slug, n=name):
            entry = get_entry_for_pos(m.start())
            anchor = ''
            if entry:
                if is_topical:
                    heading = find_heading_for_topic(s, entry)
                else:
                    heading = find_heading_for_ref(s, entry)
                if heading:
                    anchor = f'#{heading}'
            return f'<a href=\"/mind/chapter/{s}{anchor}\" class=\"idx-link\">{n}</a>'
        html = re.sub(rf'(?<![a-zA-Z/\"\'])({name})(?![a-zA-Z])', special_link, html)
    else:
        html = re.sub(rf'(?<![a-zA-Z/\"\'])({name})(?![a-zA-Z])', f'<a href=\"/mind/chapter/{slug}\" class=\"idx-link\">{name}</a>', html)

with open(idx_file, 'w') as f:
    f.write(html)
" "$idx_file" "$HEADING_MAP" "$OUTPUT_DIR/.topical-heading-map.json"
        fi
    done
    echo -e " ${GREEN}done${NC}"

    # (Appendix A was split into 12 standalone appendices A1-A12 in source MD;
    # the old section_groups generator, question-heading promoter, and
    # split_appendix_a post-processor are no longer needed.)

    # Transform "God thinks -> ... -> theology" cascade paragraphs into styled
    # vertical loop visualizations. See scripts/transform_cascades.py for details.
    echo -ne "  Transforming cognition cascades..."
    python3 "$SCRIPT_DIR/transforms/transform_cascades.py" "$OUTPUT_DIR/chapters"

    # Style code block comments (// text -> <span class="code-comment">)
    echo -ne "  Styling code blocks..."
    python3 "$SCRIPT_DIR/transforms/transform_code_blocks.py" "$OUTPUT_DIR/chapters"

    # Inject YouTube video embeds (web-only, not in PDF/EPUB)
    echo -ne "  Injecting video embeds..."
    python3 "$SCRIPT_DIR/transforms/transform_video_embeds.py" "$OUTPUT_DIR/chapters"

    echo -ne "  Wrapping Dead Sea Scrolls quotes..."
    python3 "$SCRIPT_DIR/transforms/transform_dss_cards.py" "$OUTPUT_DIR/chapters"

    echo -ne "  Injecting song chips..."
    python3 "$SCRIPT_DIR/transforms/transform_song_links.py" "$OUTPUT_DIR/chapters"

    # Inject web-only images (e.g., the Darth Vader image in Ch 19).
    # Not in PDF/EPUB/Ingram. See scripts/transform_web_only_images.py.
    echo -ne "  Injecting web-only images..."
    python3 "$SCRIPT_DIR/transforms/transform_web_only_images.py" "$OUTPUT_DIR/chapters"

    # Web-only: rewrite the Plato -> Augustine -> Tradition -> This Book lineage
    # ASCII diagram in appendix-i as a styled vertical timeline of cards.
    echo -ne "  Styling lineage diagram..."
    python3 "$SCRIPT_DIR/transforms/transform_lineage_diagram.py" "$OUTPUT_DIR/chapters"

    # Web-only: rewrite THE SENTENCE radial ASCII in appendix-b as a styled
    # quote + 5 numbered clause cards.
    echo -ne "  Styling sentence breakdown..."
    python3 "$SCRIPT_DIR/transforms/transform_sentence_breakdown.py" "$OUTPUT_DIR/chapters"

    # Web-only: rewrite the THE ETERNAL THOUGHT -> Cross/Conversion/Judgment
    # ASCII tree in chapter-02 as a styled hero card + three frame cards.
    echo -ne "  Styling eternal thought diagram..."
    python3 "$SCRIPT_DIR/transforms/transform_eternal_thought_diagram.py" "$OUTPUT_DIR/chapters"

    # Web-only: rewrite the file-tree ASCII in how-this-book-talks as a styled
    # code-editor sidebar -- owning the book-as-codebase metaphor visually.
    echo -ne "  Styling book tree diagram..."
    python3 "$SCRIPT_DIR/transforms/transform_book_tree.py" "$OUTPUT_DIR/chapters"

    # Web-only: tag Appendix N costume paragraphs (Christian appearance,
    # Platonic substrate, Damage, Framework correction) with kind classes
    # so CSS can render each costume as a 4-field diagnostic card with a
    # colored left rail per field.
    echo -ne "  Tagging costume cards..."
    python3 "$SCRIPT_DIR/transforms/transform_costume_cards.py" "$OUTPUT_DIR/chapters"

    # Web-only: wrap each objection-and-answer pair in every chapter's
    # "Objections and Answers" section as a single card -- objection as
    # quote-card header, answer paragraphs as the body.
    echo -ne "  Wrapping objection cards..."
    python3 "$SCRIPT_DIR/transforms/transform_objection_cards.py" "$OUTPUT_DIR/chapters"

    # Web-only: convert "For Further Study" verse lists into study cards
    # with each verse rendered as a chip in a flex-wrap grid.
    echo -ne "  Building study cards..."
    python3 "$SCRIPT_DIR/transforms/transform_study_cards.py" "$OUTPUT_DIR/chapters"

    # Web-only: tag short blockquotes as pull-quotes for display-style emphasis.
    echo -ne "  Tagging pull-quotes..."
    python3 "$SCRIPT_DIR/transforms/transform_pullquotes.py" "$OUTPUT_DIR/chapters"

    # Web-only: when one of THE SENTENCE's four anchor verses (Heb 11:3,
    # Col 1:17, Acts 17:28, Isa 45:7) appears inline, callout the paragraph.
    echo -ne "  Highlighting anchor verses..."
    python3 "$SCRIPT_DIR/transforms/transform_anchor_verses.py" "$OUTPUT_DIR/chapters"

    # Manual asterisk endnotes: link each `word*` marker to its `<p>* ...` note
    # so the reader can click from marker to note and back. The PDF adds page
    # pointers; on the web it is a plain jump. See scripts/lib/footnote_refs.py.
    echo -ne "  Linking asterisk footnotes..."
    python3 "$SCRIPT_DIR/lib/footnote_refs.py" "$OUTPUT_DIR/chapters"

    # Annotate every chapter in chapters.json with word_count + read_time_minutes
    # so the chapter template can show "~12 min read" under the title.
    echo -ne "  Computing reading times..."
    python3 "$SCRIPT_DIR/add_reading_times.py" "$OUTPUT_DIR"

    # Annotate chapters.json with first-sentence `teaser` per chapter so the
    # chapter template can render a "Next: ..." card with a body preview.
    echo -ne "  Extracting chapter teasers..."
    python3 "$SCRIPT_DIR/add_chapter_teasers.py" "$OUTPUT_DIR"

    # Extract appendix-r glossary into a JSON map for runtime tooltip lookup.
    echo -ne "  Extracting glossary..."
    python3 "$SCRIPT_DIR/extract_glossary.py" "$OUTPUT_DIR"

    # Copy cover images (web + PDF versions)
    COVER_WEB="$BOOK_SOURCE_DIR/covers/bookCover-web.jpeg"
    COVER_PDF="$BOOK_SOURCE_DIR/covers/bookCover-pdf.jpeg"
    if [ -f "$COVER_WEB" ]; then
        echo -ne "  Copying cover image..."
        cp "$COVER_WEB" "$OUTPUT_DIR/covers/"
        [ -f "$COVER_PDF" ] && cp "$COVER_PDF" "$OUTPUT_DIR/covers/"
        echo -e " ${GREEN}done${NC}"
    else
        echo -e "  ${YELLOW}Warning: Cover image not found${NC}"
    fi

    # Copy inline chapter images. For each image referenced in markdown as
    # src="foo.ext", prefer a web-optimized variant "foo-web.jpg" if present
    # (full-res original stays for PDF/EPUB/print). Rewrite src to absolute
    # /book-content/images/<chosen>.
    mkdir -p "$OUTPUT_DIR/images"
    INLINE_IMAGE_COUNT=0
    for img in "$BOOK_SOURCE_DIR"/*.png "$BOOK_SOURCE_DIR"/*.jpg "$BOOK_SOURCE_DIR"/*.jpeg; do
        [ -f "$img" ] || continue
        fname=$(basename "$img")
        # Skip variant images (web/print) — they're used by their base images' pipelines
        case "$fname" in *-web.jpg|*-web.jpeg|*-web.png|*-print.jpg|*-print.jpeg|*-print.png) continue ;; esac

        stem="${fname%.*}"
        web_variant=""
        for cand in "$BOOK_SOURCE_DIR/${stem}-web.jpg" "$BOOK_SOURCE_DIR/${stem}-web.jpeg" "$BOOK_SOURCE_DIR/${stem}-web.png"; do
            if [ -f "$cand" ]; then
                web_variant=$(basename "$cand")
                break
            fi
        done

        if [ -n "$web_variant" ]; then
            cp "$BOOK_SOURCE_DIR/$web_variant" "$OUTPUT_DIR/images/$web_variant"
            # Content-based cache-buster (file size) — re-uploads get a new URL,
            # and it sidesteps any stale Cloudflare cache (incl. cached 404s).
            ver=$(stat -f%z "$OUTPUT_DIR/images/$web_variant")
            # Rewrite references from original to the web variant
            for html in "$OUTPUT_DIR/chapters"/*.html; do
                [ -f "$html" ] || continue
                sed -i '' "s|src=\"$fname\"|src=\"/book-content/images/$web_variant?v=$ver\"|g" "$html"
            done
        else
            cp "$img" "$OUTPUT_DIR/images/$fname"
            ver=$(stat -f%z "$OUTPUT_DIR/images/$fname")
            for html in "$OUTPUT_DIR/chapters"/*.html; do
                [ -f "$html" ] || continue
                sed -i '' "s|src=\"$fname\"|src=\"/book-content/images/$fname?v=$ver\"|g" "$html"
            done
        fi
        INLINE_IMAGE_COUNT=$((INLINE_IMAGE_COUNT + 1))
    done
    if [ "$INLINE_IMAGE_COUNT" -gt 0 ]; then
        echo -e "  Copying inline images... ${GREEN}done${NC} ($INLINE_IMAGE_COUNT files)"
    fi

    # ─── Post-build HTML transforms ───
    # These modify the generated HTML for web display only.
    # The markdown source stays unchanged (used for PDF/EPUB).
    POST_BUILD_DIR="$OUTPUT_DIR/chapters"
    if [ -d "$POST_BUILD_DIR" ]; then
        echo -ne "  Applying post-build HTML transforms..."

        # Appendix C: merge first two columns (# + Distinctive) into one
        APPC="$POST_BUILD_DIR/appendix-c.html"
        if [ -f "$APPC" ]; then
            # Replace 6-col header with 5-col (drop # column, rename Distinctive)
            sed -i '' '/<th>#<\/th>/{N;s/<th>#<\/th>\n<th>Distinctive<\/th>/<th>Distinctive<\/th>/;}' "$APPC"
            # Merge numbered td + bold td pairs into single td: <td>1</td>\n<td><strong>X</strong></td> → <td><strong>1. X</strong></td>
            sed -i '' '/<td>[0-9]\{1,2\}<\/td>/{N;s/<td>\([0-9]\{1,2\}\)<\/td>\n<td><strong>\(.*\)<\/strong><\/td>/<td><strong>\1. \2<\/strong><\/td>/;}' "$APPC"
            # Update colgroup: 6 cols → 5 cols at 20% each
            sed -i '' '/<col style="width: 16%" \/>/{
                N;N;N;N;N
                s/<col style="width: 16%" \/>\n<col style="width: 16%" \/>\n<col style="width: 16%" \/>\n<col style="width: 16%" \/>\n<col style="width: 16%" \/>\n<col style="width: 16%" \/>/<col style="width: 20%" \/>\n<col style="width: 20%" \/>\n<col style="width: 20%" \/>\n<col style="width: 20%" \/>\n<col style="width: 20%" \/>/
            }' "$APPC"
        fi

        # Paragraph-precise topical index (Appendix Q): stamp <span id="ix-..">
        # anchors into each section's HTML and rebuild appendix-q.html as the A-Z
        # index whose entries deep-link across pages to those anchors. Runs LAST so
        # the anchors land in the final HTML. See scripts/inject_web_index.py.
        if [ -f "$BOOK_SOURCE_DIR/index-data/topical-index.json" ]; then
            python3 "$SCRIPT_DIR/inject_web_index.py" "$POST_BUILD_DIR" "$BOOK_SOURCE_DIR/index-data/topical-index.json"
        fi

        # Glossary (Appendix R): stamp <span id="glx-.."> discussion anchors into each
        # section's HTML and turn the glossary's plain-text "See Chapter N" refs into
        # precise deep links (/mind/chapter/<slug>#glx-..). Runs after the topical index
        # so both anchor sets coexist. See scripts/inject_web_glossary.py.
        if [ -f "$BOOK_SOURCE_DIR/index-data/glossary-index.json" ]; then
            python3 "$SCRIPT_DIR/inject_web_glossary.py" "$POST_BUILD_DIR" "$BOOK_SOURCE_DIR/index-data/glossary-index.json"
        fi

        # Add more post-build transforms here as needed

        echo -e " ${GREEN}done${NC}"
    fi

    echo ""
fi

# =============================================================================
# MODE: EPUB  —  pandoc EPUB for pristinegrace.org download (fast, no PDF render)
# =============================================================================
if [ "$BUILD" = true ] && [ "$BUILD_EPUB" = true ]; then
    echo -e "${BLUE}▸ EPUB${NC}"

    mkdir -p "$OUTPUT_DIR/downloads"

    # Build EPUB from source markdown
    echo -ne "  Building EPUB..."
    EPUB_FILE="$BOOK_SOURCE_DIR/A-Thought-in-the-Mind-of-God.epub"
    COVER_IMG="$BOOK_SOURCE_DIR/covers/bookCover-ebook.jpg"
    # Combine all markdown files in order, stripping frontmatter
    COMBINED_MD=$(mktemp)
    # Applied appendices are appendix-a1..a12 (NOT zero-padded), so a plain
    # appendix-*.md glob sorts them lexicographically (A1, A10, A11, A12, A2, ...).
    # Collect A1..A12 in numeric order, then the single-letter appendices B..Z,
    # matching the PDF builder's collect_appendices().
    APPENDIX_FILES=()
    for n in $(seq 1 12); do
        for f in "$BOOK_SOURCE_DIR"/appendix-a${n}-*.md; do
            [ -f "$f" ] && APPENDIX_FILES+=("$f")
        done
    done
    for f in "$BOOK_SOURCE_DIR"/appendix-[b-z]*.md; do
        [ -f "$f" ] && APPENDIX_FILES+=("$f")
    done
    for md_file in \
        "$BOOK_SOURCE_DIR/front-matter/01-half-title.md" \
        "$BOOK_SOURCE_DIR/front-matter/02-title-page.md" \
        "$BOOK_SOURCE_DIR/front-matter/03-copyright.md" \
        "$BOOK_SOURCE_DIR/front-matter/04-dedication.md" \
        "$BOOK_SOURCE_DIR/front-matter/foreword.md" \
        "$BOOK_SOURCE_DIR/preface.md" \
        "$BOOK_SOURCE_DIR/front-matter/06-acknowledgments.md" \
        "$BOOK_SOURCE_DIR/prologue.md" \
        "$BOOK_SOURCE_DIR/how-this-book-talks.md" \
        "$BOOK_SOURCE_DIR"/chapter-[0-9]*.md \
        "$BOOK_SOURCE_DIR/epilogue.md" \
        "$BOOK_SOURCE_DIR/afterword.md" \
        "${APPENDIX_FILES[@]}" \
        "$BOOK_SOURCE_DIR/about-the-author.md" \
        "$BOOK_SOURCE_DIR/grace-and-peace.md"; do
        if [ -f "$md_file" ]; then
            strip_frontmatter "$md_file" >> "$COMBINED_MD"
            echo -e "\n\n" >> "$COMBINED_MD"
        fi
    done
    # Add cross-reference links to combined markdown before pandoc
    python3 -c "
import re, glob, os

book_dir = '$BOOK_SOURCE_DIR'

# Build heading ID map from source files
id_map = {}
for cf in sorted(glob.glob(os.path.join(book_dir, 'chapter-[0-9]*.md'))):
    for line in open(cf):
        m = re.match(r'^#\s+Chapter\s+(\d+):\s+(.+)', line)
        if m:
            num = int(m.group(1))
            title = m.group(2).strip()
            full = f'chapter-{num}-{title}'
            slug = re.sub(r'[^\w\s-]', '', full.lower()).strip()
            slug = re.sub(r'[\s]+', '-', slug)
            slug = re.sub(r'-+', '-', slug)
            id_map[('chapter', num)] = slug
            break
# Iterate ALL appendix files (not by single letter) and capture the full key
# including applied-appendix numbers (A1..A12) so e.g. 'App. A6' links, not just 'App. N'.
for path in sorted(glob.glob(os.path.join(book_dir, 'appendix-*.md'))):
    for line in open(path):
        m = re.match(r'^#\s+Appendix\s+([A-Z][0-9]*):\s+(.+)', line)
        if m:
            key = m.group(1).upper()
            full = f'appendix-{key.lower()}-{m.group(2).strip()}'
            slug = re.sub(r'[^\w\s-]', '', full.lower()).strip()
            slug = re.sub(r'[\s]+', '-', slug)
            slug = re.sub(r'-+', '-', slug)
            id_map[('appendix', key)] = slug
            break
for name, filename in [('prologue', 'prologue.md'), ('preface', 'preface.md'),
                       ('epilogue', 'epilogue.md')]:
    fp = os.path.join(book_dir, filename)
    if os.path.exists(fp):
        for line in open(fp):
            m = re.match(r'^#\s+(.+)', line)
            if m:
                slug = re.sub(r'[^\w\s-]', '', m.group(1).strip().lower()).strip()
                slug = re.sub(r'[\s]+', '-', slug)
                slug = re.sub(r'-+', '-', slug)
                id_map[('special', name)] = slug
                break

with open('$COMBINED_MD', 'r') as f:
    text = f.read()

lines = text.split('\n')
new_lines = []
for line in lines:
    # Skip H1 headings (don't link the heading itself)
    if line.startswith('# '):
        new_lines.append(line)
        continue

    # Chapter N / Ch. N
    def repl_ch(m):
        prefix, num = m.group(1), int(m.group(2))
        key = ('chapter', num)
        if key in id_map:
            return f'[{prefix} {num}](#{id_map[key]})'
        return m.group(0)
    line = re.sub(r'(?<!\[)(Chapter|Ch\.)\s+(\d+)(?!\d)(?!\])', repl_ch, line)

    # Appendix X / App. X -- key may be a single letter (N) or applied (A1..A12)
    def repl_app(m):
        prefix, key = m.group(1), m.group(2).upper()
        k = ('appendix', key)
        if k in id_map:
            return f'[{prefix} {m.group(2)}](#{id_map[k]})'
        return m.group(0)
    line = re.sub(r'(?<!\[)(Appendix|App\.)\s+([A-Z][0-9]*)(?![a-z])(?!\])', repl_app, line)

    # Prologue, Preface, Epilogue
    for sname in ['Prologue', 'Preface', 'Epilogue']:
        key = ('special', sname.lower())
        if key in id_map:
            line = re.sub(rf'(?<!\[)\b({sname})\b(?!\]|\()', rf'[\1](#{id_map[key]})', line)

    new_lines.append(line)

with open('$COMBINED_MD', 'w') as f:
    f.write('\n'.join(new_lines))
" 2>/dev/null
    # Inject Related Appendices after For Further Study sections
    python3 -c "
import sys, re
sys.path.insert(0, '$SCRIPT_DIR/lib')
from crossrefs import build_crossref_map, inject_related_appendices

ch_map, app_map = build_crossref_map('$BOOK_SOURCE_DIR')

with open('$COMBINED_MD') as f:
    text = f.read()

text = inject_related_appendices(text, ch_map, link_prefix='#')

with open('$COMBINED_MD', 'w') as f:
    f.write(text)
" 2>/dev/null
    # Swap <img src="foo.png"> to foo-web.jpg when a web variant exists so the
    # EPUB embeds the small version rather than the multi-megabyte original.
    # Also fall back to a light-background foo-light.* so diagrams authored dark
    # for the dark web theme render light in the EPUB, matching the paper-white
    # PDF (e-readers default to a light page). Photos without a -light variant
    # are left untouched.
    python3 -c "
import os, re
src_dir = '$BOOK_SOURCE_DIR'
with open('$COMBINED_MD') as f:
    text = f.read()
def repl(m):
    src = m.group(1)
    if '://' in src or '-web.' in src or '-print.' in src or '-light.' in src:
        return m.group(0)
    stem, ext = os.path.splitext(src)
    for cand in (f'{stem}-web.jpg', f'{stem}-web.jpeg', f'{stem}-web.png',
                 f'{stem}-light.png', f'{stem}-light.jpg'):
        if os.path.exists(os.path.join(src_dir, cand)):
            return f'src=\"{cand}\"'
    return m.group(0)
text = re.sub(r'src=\"([^\"]+)\"', repl, text)
with open('$COMBINED_MD', 'w') as f:
    f.write(text)
" 2>/dev/null
    # Inject the paragraph-precise topical index (anchors + linked, nested entries)
    # into the combined markdown; pandoc rewrites the cross-file #ix-... links.
    python3 "$SCRIPT_DIR/inject_epub_index.py" "$COMBINED_MD" "$BOOK_SOURCE_DIR/index-data/topical-index.json"
    # Retarget the glossary's "See Chapter N" links to the exact discussion paragraph
    # (stamps glx-anchors + rewrites the entry links); pandoc rewrites the cross-file
    # #glx-... links. Runs AFTER the index injector so both anchor sets coexist.
    python3 "$SCRIPT_DIR/inject_epub_glossary.py" "$COMBINED_MD" "$BOOK_SOURCE_DIR/index-data/glossary-index.json"
    # Swap inline photo/illustration <img>s to compressed -web.jpg variants so the
    # EPUB stays light (full-res originals are print-only). Any base image that has
    # a {stem}-web.jpg sibling gets rewritten; diagram -light plates are untouched.
    for wv in "$BOOK_SOURCE_DIR"/*-web.jpg; do
        [ -f "$wv" ] || continue
        base=$(basename "$wv" -web.jpg)
        sed -i '' "s|src=\"${base}\.png\"|src=\"${base}-web.jpg\"|g; s|src=\"${base}\.jpg\"|src=\"${base}-web.jpg\"|g; s|src=\"${base}\.jpeg\"|src=\"${base}-web.jpg\"|g" "$COMBINED_MD"
    done
    pandoc "$COMBINED_MD" --from markdown+smart --to epub3 --output "$EPUB_FILE" \
        --resource-path="$BOOK_SOURCE_DIR" \
        --metadata title="A Thought in the Mind of God" \
        --metadata author="Brandan Kraft" \
        --metadata lang=en \
        --metadata publisher="Pristine Grace Publishing" \
        --epub-cover-image "$COVER_IMG" \
        --toc --toc-depth=1 --split-level=1 --epub-title-page=false 2>/dev/null
    rm -f "$COMBINED_MD"
    # Bring the EPUB to parity with web/PDF: DSS cards, pull-quotes, and the five
    # charts, plus reader-safe CSS (post-processes the built epub in place).
    python3 "$SCRIPT_DIR/epub_enhance.py" "$EPUB_FILE" "$BOOK_SOURCE_DIR"
    EPUB_SIZE=$(du -h "$EPUB_FILE" | cut -f1 | xargs)
    echo -e " ${GREEN}done${NC} ($EPUB_SIZE)"
    cp "$EPUB_FILE" "$OUTPUT_DIR/downloads/"

    echo ""
fi

# =============================================================================
# MODE: PDF  —  Web PDF for pristinegrace.org download (weasyprint render)
# =============================================================================
if [ "$BUILD" = true ] && [ "$BUILD_PDF" = true ]; then
    echo -e "${BLUE}▸ Web PDF${NC}"

    mkdir -p "$OUTPUT_DIR/downloads"

    # Build PDF from source markdown
    echo -ne "  Building PDF..."
    PDF_FILE="$BOOK_SOURCE_DIR/A-Thought-in-the-Mind-of-God.pdf"
    BACK_COVER="$BOOK_SOURCE_DIR/covers/backCover-pdf.jpeg"
    python3 "$SCRIPT_DIR/build-book-pdf.py" "$BOOK_SOURCE_DIR" "$PDF_FILE" 2>/dev/null
    if [ -f "$PDF_FILE" ]; then
        PDF_SIZE=$(du -h "$PDF_FILE" | cut -f1 | xargs)
        echo -e " ${GREEN}done${NC} ($PDF_SIZE)"
        python3 "$SCRIPT_DIR/audit_pdf.py" "$PDF_FILE" --trim web-pdf || echo -e "  ${RED}⚠️  PDF AUDIT FAILED -- review above before uploading${NC}"
        cp "$PDF_FILE" "$OUTPUT_DIR/downloads/"
    else
        echo -e "  ${YELLOW}Warning: PDF not found at $PDF_FILE${NC}"
    fi

    echo ""
fi

# =============================================================================
# MODE: INGRAM  —  IngramSpark interior PDF(s) (local only, not deployed)
# =============================================================================
if [ "$BUILD" = true ] && [ "$BUILD_INGRAM" = true ]; then
    # IngramSpark is now a SINGLE 8.5x11 hardcover volume (decided 2026-06-02).
    # The full book is ~784 pages, well under Ingram's 1200-page cap for 8.5x11
    # B&W on 50# white. No --volume flag = the whole book as one interior.
    echo -e "${BLUE}▸ IngramSpark interior (single 8.5x11 hardcover volume)${NC}"

    INGRAM_DIR="$BOOK_SOURCE_DIR/ingramspark"
    mkdir -p "$INGRAM_DIR"

    INGRAM_PDF="$INGRAM_DIR/A-Thought-in-the-Mind-of-God-8.5x11-hardcover.pdf"
    echo -ne "  Building single-volume hardcover interior..."
    python3 "$SCRIPT_DIR/build-book-pdf.py" "$BOOK_SOURCE_DIR" "$INGRAM_PDF" --ingram 2>/dev/null
    if [ -f "$INGRAM_PDF" ]; then
        INGRAM_SIZE=$(du -h "$INGRAM_PDF" | cut -f1 | xargs)
        echo -e " ${GREEN}done${NC} ($INGRAM_SIZE)"
        python3 "$SCRIPT_DIR/audit_pdf.py" "$INGRAM_PDF" --trim 8.5x11 || echo -e "  ${RED}⚠️  PDF AUDIT FAILED -- review above before uploading${NC}"
    else
        echo -e "  ${RED}IngramSpark build failed${NC}"
    fi

    # --- DUAL-VOLUME BUILD RETIRED 2026-06-02 (kept for reference) ---
    # We no longer generate Volume I / Volume II. Restore this block if a
    # two-volume set is ever needed again.
    #
    # VOL1_PDF="$INGRAM_DIR/volume-1-the-book.pdf"
    # echo -ne "  Building Volume I: The Book..."
    # python3 "$SCRIPT_DIR/build-book-pdf.py" "$BOOK_SOURCE_DIR" "$VOL1_PDF" --ingram --volume 1 2>/dev/null
    # if [ -f "$VOL1_PDF" ]; then
    #     VOL1_SIZE=$(du -h "$VOL1_PDF" | cut -f1 | xargs)
    #     echo -e " ${GREEN}done${NC} ($VOL1_SIZE)"
    # else
    #     echo -e "  ${RED}Volume I build failed${NC}"
    # fi
    #
    # VOL2_PDF="$INGRAM_DIR/volume-2-the-toolkit.pdf"
    # echo -ne "  Building Volume II: The Toolkit..."
    # # Pass Vol 1 PDF so pass 3 can emit cross-volume index references (V1:/V2:).
    # python3 "$SCRIPT_DIR/build-book-pdf.py" "$BOOK_SOURCE_DIR" "$VOL2_PDF" --ingram --volume 2 --vol1-pdf "$VOL1_PDF" 2>/dev/null
    # if [ -f "$VOL2_PDF" ]; then
    #     VOL2_SIZE=$(du -h "$VOL2_PDF" | cut -f1 | xargs)
    #     echo -e " ${GREEN}done${NC} ($VOL2_SIZE)"
    # else
    #     echo -e "  ${RED}Volume II build failed${NC}"
    # fi

    echo ""
fi

# =============================================================================
# MODE: 6X9  —  6x9 B&W paperback interior PDF (local only, not deployed)
# =============================================================================
if [ "$BUILD" = true ] && [ "$BUILD_6X9" = true ]; then
    # 6x9 affordable paperback edition. Same Ingram-style running heads / folios /
    # alternating gutters as the 8.5x11 interior, but a 6x9 trim at 10.5pt so the
    # longer reflow (~1,070 pages) still fits one volume under the 1,200 B&W cap.
    # Color 6x9 is impossible (over the ~840-900 color caps); this is B&W-only.
    echo -e "${BLUE}▸ 6x9 paperback interior (10.5pt, single volume)${NC}"

    SIXBY9_DIR="$BOOK_SOURCE_DIR/ingramspark"
    mkdir -p "$SIXBY9_DIR"

    SIXBY9_PDF="$SIXBY9_DIR/A-Thought-in-the-Mind-of-God-6x9.pdf"
    echo -ne "  Building 6x9 interior..."
    python3 "$SCRIPT_DIR/build-book-pdf.py" "$BOOK_SOURCE_DIR" "$SIXBY9_PDF" --6x9 2>/dev/null
    if [ -f "$SIXBY9_PDF" ]; then
        SIXBY9_SIZE=$(du -h "$SIXBY9_PDF" | cut -f1 | xargs)
        echo -e " ${GREEN}done${NC} ($SIXBY9_SIZE)"
        python3 "$SCRIPT_DIR/audit_pdf.py" "$SIXBY9_PDF" --trim 6x9 || echo -e "  ${RED}⚠️  PDF AUDIT FAILED -- review above before uploading${NC}"
    else
        echo -e "  ${RED}6x9 build failed${NC}"
    fi
    echo ""
fi

# =============================================================================
# MODE: 7X10  —  7x10 textbook interior PDF (local only, not deployed)
# =============================================================================
if [ "$BUILD" = true ] && [ "$BUILD_7X10" = true ]; then
    # 7x10 traditional textbook edition. Full 11pt body (no size drop needed),
    # Ingram running heads / folios / alternating gutters, flat print-safe tints.
    # Ingram's 7x10 cap is 1,200 pages for BOTH B&W and color, so this trim can
    # carry the full-color edition in one volume (verified 2026-06-10).
    echo -e "${BLUE}▸ 7x10 textbook interior (11pt, single volume)${NC}"

    SEVENBY10_DIR="$BOOK_SOURCE_DIR/ingramspark"
    mkdir -p "$SEVENBY10_DIR"

    SEVENBY10_PDF="$SEVENBY10_DIR/A-Thought-in-the-Mind-of-God-7x10.pdf"
    echo -ne "  Building 7x10 interior..."
    python3 "$SCRIPT_DIR/build-book-pdf.py" "$BOOK_SOURCE_DIR" "$SEVENBY10_PDF" --7x10 2>/dev/null
    if [ -f "$SEVENBY10_PDF" ]; then
        SEVENBY10_SIZE=$(du -h "$SEVENBY10_PDF" | cut -f1 | xargs)
        echo -e " ${GREEN}done${NC} ($SEVENBY10_SIZE)"
        python3 "$SCRIPT_DIR/audit_pdf.py" "$SEVENBY10_PDF" --trim 7x10 || echo -e "  ${RED}⚠️  PDF AUDIT FAILED -- review above before uploading${NC}"
    else
        echo -e "  ${RED}7x10 build failed${NC}"
    fi
    echo ""
fi

# =============================================================================
# MODE: 7X10BW  —  7x10 B&W interior PDF (local only, not deployed)
# Same trim/pagination as the color 7x10, grayscaled. ONE interior serves BOTH
# the B&W paperback (ISBN ...-2-9) and the B&W hardcover (ISBN ...-4-3); only the
# covers differ. Audited against the 7x10 baseline (identical page count).
# =============================================================================
if [ "$BUILD" = true ] && [ "$BUILD_7X10BW" = true ]; then
    echo -e "${BLUE}▸ 7x10 B&W interior (11pt, single volume, grayscale)${NC}"

    SEVENBY10BW_DIR="$BOOK_SOURCE_DIR/ingramspark"
    mkdir -p "$SEVENBY10BW_DIR"

    SEVENBY10BW_PDF="$SEVENBY10BW_DIR/A-Thought-in-the-Mind-of-God-7x10-bw.pdf"
    echo -ne "  Building 7x10 B&W interior..."
    python3 "$SCRIPT_DIR/build-book-pdf.py" "$BOOK_SOURCE_DIR" "$SEVENBY10BW_PDF" --7x10bw 2>/dev/null
    if [ -f "$SEVENBY10BW_PDF" ]; then
        SEVENBY10BW_SIZE=$(du -h "$SEVENBY10BW_PDF" | cut -f1 | xargs)
        echo -e " ${GREEN}done${NC} ($SEVENBY10BW_SIZE)"
        python3 "$SCRIPT_DIR/audit_pdf.py" "$SEVENBY10BW_PDF" --trim 7x10 || echo -e "  ${RED}⚠️  PDF AUDIT FAILED -- review above before uploading${NC}"
    else
        echo -e "  ${RED}7x10 B&W build failed${NC}"
    fi
    echo ""
fi

# =============================================================================
# SUMMARY
# =============================================================================
echo -e "  ${GREEN}Done.${NC}"
if [ "$BUILD_WEB" = true ] && [ "$HTML_COUNT" -gt 0 ]; then
    echo -e "  Web: ${HTML_COUNT} HTML files built"
fi
if [ "$BUILD_WEB" = true ] || [ "$BUILD_PDF" = true ]; then
    echo -e "  ${YELLOW}To publish: run${NC} ./scripts/deploy.sh \"message\""
fi
echo ""
