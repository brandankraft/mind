#!/usr/bin/env python3
"""
Add Red Letter markers to kjv.json using CrossWire OSIS XML.

Parses <q who="Jesus"> elements from CrossWire's KJV OSIS XML and inserts
<r>...</r> markers around the words of Christ in kjv.json verse text.

Usage:
    python3 scripts/add_red_letter_markers.py [--xml /path/to/kjvfull.xml] [--dry-run]

The script:
1. Parses CrossWire XML to identify which text in each verse is spoken by Jesus
2. Extracts the plain text of those portions
3. Matches them against kjv.json verse text and wraps with <r>...</r>
4. Writes the updated kjv.json

CrossWire XML structure:
- Verses are milestones: <verse sID="Matt.1.1"/>...text...<verse eID="Matt.1.1"/>
- Jesus quotes: <q who="Jesus"> containing <w> (words) and <transChange> elements
- Quotes can span multiple verses (280 of 648 do)
"""

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

NS = 'http://www.bibletechnologies.net/2003/OSIS/namespace'

# CrossWire OSIS book names → kjv.json book abbreviations
OSIS_TO_KJV = {
    # NT books (where Jesus quotes appear)
    'Matt': 'mt', 'Mark': 'mk', 'Luke': 'lk', 'John': 'jo',
    'Acts': 'act', 'Rom': 'rm', '1Cor': '1co', '2Cor': '2co',
    'Gal': 'gl', 'Eph': 'eph', 'Phil': 'ph', 'Col': 'cl',
    '1Thess': '1ts', '2Thess': '2ts', '1Tim': '1tm', '2Tim': '2tm',
    'Titus': 'tt', 'Phlm': 'phm', 'Heb': 'hb', 'Jas': 'jm',
    '1Pet': '1pe', '2Pet': '2pe', '1John': '1jo', '2John': '2jo',
    '3John': '3jo', 'Jude': 'jd', 'Rev': 're',
    # OT books
    'Gen': 'gn', 'Exod': 'ex', 'Lev': 'lv', 'Num': 'nm', 'Deut': 'dt',
    'Josh': 'js', 'Judg': 'jud', 'Ruth': 'rt', '1Sam': '1sm', '2Sam': '2sm',
    '1Kgs': '1kgs', '2Kgs': '2kgs', '1Chr': '1ch', '2Chr': '2ch',
    'Ezra': 'ezr', 'Neh': 'ne', 'Esth': 'et', 'Job': 'job',
    'Ps': 'ps', 'Prov': 'prv', 'Eccl': 'ec', 'Song': 'so',
    'Isa': 'is', 'Jer': 'jr', 'Lam': 'lm', 'Ezek': 'ez', 'Dan': 'dn',
    'Hos': 'ho', 'Joel': 'jl', 'Amos': 'am', 'Obad': 'ob',
    'Jonah': 'jn', 'Mic': 'mi', 'Nah': 'na', 'Hab': 'hk',
    'Zeph': 'zp', 'Hag': 'hg', 'Zech': 'zc', 'Mal': 'ml',
}


def extract_text_from_element(elem):
    """Extract plain text from an OSIS element, handling <w>, <transChange>, etc."""
    parts = []
    if elem.text:
        parts.append(elem.text)
    for child in elem:
        tag = child.tag.split('}')[1] if '}' in child.tag else child.tag
        if tag in ('w', 'transChange', 'seg', 'divineName', 'hi', 'foreign',
                    'rdg', 'catchWord', 'inscription'):
            # Recursively extract text from these elements
            parts.append(extract_text_from_element(child))
        elif tag == 'milestone':
            pass  # Skip milestones
        elif tag == 'verse':
            pass  # Skip verse milestones inside quotes
        elif tag == 'q':
            # Nested quote — still extract text
            parts.append(extract_text_from_element(child))
        elif tag == 'note':
            pass  # Skip notes (margin notes, etc.)
        elif tag == 'title':
            pass  # Skip titles
        elif tag == 'lg' or tag == 'l':
            # Poetry lines — extract text
            parts.append(extract_text_from_element(child))
        else:
            # Unknown tag — still try to get text
            parts.append(extract_text_from_element(child))

        if child.tail:
            parts.append(child.tail)

    return ''.join(parts)


def parse_verse_ref(osisID):
    """Parse an OSIS verse ID like 'Matt.3.15' into (book, chapter, verse)."""
    parts = osisID.split('.')
    if len(parts) != 3:
        return None
    return (parts[0], int(parts[1]), int(parts[2]))


def extract_red_letter_map(xml_path):
    """
    Parse CrossWire OSIS XML and build a map of verse → red letter text segments.

    Returns:
        dict: {(book, chapter, verse) → [text_segment, ...]}
        Each text_segment is the plain text that should be red.
    """
    print(f"Parsing CrossWire OSIS XML: {xml_path}")
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Strategy: Walk the entire document linearly, tracking current verse.
    # When inside a <q who="Jesus">, collect text per verse.

    red_map = defaultdict(list)  # (book, ch, vs) → [text segments]

    def process_body(body_elem):
        """Walk the OSIS body building the red letter map."""
        current_verse = None  # (book, chapter, verse) tuple
        in_jesus_quote_depth = 0  # nesting depth of <q who="Jesus">

        def walk(elem, collecting=False):
            nonlocal current_verse, in_jesus_quote_depth

            tag = elem.tag.split('}')[1] if '}' in elem.tag else elem.tag

            # Track verse boundaries
            if tag == 'verse':
                sid = elem.get('sID')
                eid = elem.get('eID')
                if sid:
                    ref = parse_verse_ref(sid)
                    if ref:
                        current_verse = ref
                elif eid:
                    # Verse ended — don't clear current_verse yet,
                    # next sID will update it
                    pass
                # Process tail
                if elem.tail and collecting and current_verse:
                    text = elem.tail.strip()
                    if text:
                        red_map[current_verse].append(elem.tail)
                return

            # Handle <q who="Jesus"> elements
            if tag == 'q' and elem.get('who') == 'Jesus':
                in_jesus_quote_depth += 1

                # Process text content of this q element per-verse
                # We need to walk children and track verse changes
                if elem.text and current_verse:
                    red_map[current_verse].append(elem.text)

                for child in elem:
                    walk(child, collecting=True)

                in_jesus_quote_depth -= 1

                # Process tail (text after closing </q>)
                if elem.tail and collecting and current_verse:
                    red_map[current_verse].append(elem.tail)
                elif elem.tail and in_jesus_quote_depth > 0 and current_verse:
                    red_map[current_verse].append(elem.tail)
                return

            # Handle other elements
            if tag in ('w', 'transChange', 'seg', 'divineName', 'hi',
                       'foreign', 'rdg', 'inscription'):
                if collecting or in_jesus_quote_depth > 0:
                    if current_verse:
                        text = extract_text_from_element(elem)
                        if text.strip():
                            red_map[current_verse].append(text)
                # Process tail
                if elem.tail:
                    if (collecting or in_jesus_quote_depth > 0) and current_verse:
                        red_map[current_verse].append(elem.tail)
                return

            if tag == 'note':
                # Skip notes but process tail
                if elem.tail and (collecting or in_jesus_quote_depth > 0) and current_verse:
                    red_map[current_verse].append(elem.tail)
                return

            if tag == 'milestone':
                if elem.tail and (collecting or in_jesus_quote_depth > 0) and current_verse:
                    red_map[current_verse].append(elem.tail)
                return

            # For container elements (div, chapter, p, lg, l, etc.), recurse
            if elem.text and (collecting or in_jesus_quote_depth > 0) and current_verse:
                red_map[current_verse].append(elem.text)

            for child in elem:
                walk(child, collecting)

            if elem.tail and (collecting or in_jesus_quote_depth > 0) and current_verse:
                red_map[current_verse].append(elem.tail)

        walk(body_elem)

    # Find the osisText body
    for elem in root.iter('{%s}osisText' % NS):
        process_body(elem)
        break

    # Clean up: join segments per verse and normalize whitespace
    cleaned_map = {}
    for verse_ref, segments in red_map.items():
        full_text = ''.join(segments)
        # Normalize whitespace
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        if full_text:
            cleaned_map[verse_ref] = full_text

    return cleaned_map


def normalize_for_matching(text):
    """Normalize text for fuzzy matching between CrossWire and KJV text."""
    # Normalize curly quotes to straight apostrophes first
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    # Remove all punctuation except apostrophes for matching
    text = re.sub(r'[^\w\s\']', '', text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text.lower()


def get_kjv_plain_text(verse_text):
    """Extract plain text from kjv.json verse text (strip markers but keep italic words).

    In kjv.json:
    - {single word} = italic (added) word — part of the verse text
    - {catchword...: note text} = margin note — not part of verse text
    The margin note pattern has a colon separator.
    """
    # Remove margin notes (catchword: note patterns) but keep italic words
    # Margin notes contain ": " after the catchword
    text = re.sub(r'\{[^}]*:[ ][^}]*\}', '', verse_text)
    # Now remaining {word} are italic words — just strip the braces
    text = re.sub(r'\{([^}]+)\}', r'\1', text)
    # Remove [Psalm titles]
    text = re.sub(r'^\[.+?\]\s*', '', text)
    # Remove existing <r>...</r> markers (if re-running)
    text = re.sub(r'<r>(.*?)</r>', r'\1', text)
    # Remove <i>...</i> markers (keep content)
    text = re.sub(r'<i>(.*?)</i>', r'\1', text)
    return text.strip()


def find_red_text_boundaries(verse_text, red_text):
    """
    Find where the red letter text appears in the verse text and wrap it with <r>...</r>.

    This needs to handle:
    - {footnote} markers in the middle of red text
    - <i>italic</i> markers
    - Punctuation differences between CrossWire and KJV text
    - Partial verse coverage (only part of verse is red)

    Returns the verse text with <r>...</r> markers, or None if matching fails.
    """
    # Get plain text of the verse for matching
    plain_verse = get_kjv_plain_text(verse_text)
    plain_verse_norm = normalize_for_matching(plain_verse)
    red_text_norm = normalize_for_matching(red_text)

    # Check if the entire verse is red (most common case)
    if red_text_norm == plain_verse_norm:
        return wrap_entire_verse(verse_text)

    # Check if red text covers almost the entire verse (allow for very minor variations
    # like punctuation differences, but NOT narrative intros like "Saying,")
    if len(red_text_norm) > len(plain_verse_norm) * 0.97:
        return wrap_entire_verse(verse_text)

    # Try to find the red portion within the verse
    # Build word-level matching
    red_words = red_text_norm.split()
    verse_words = plain_verse_norm.split()

    if not red_words or not verse_words:
        return None

    # Find the starting position of red text in verse
    start_idx = find_word_sequence(verse_words, red_words)
    if start_idx is not None:
        return wrap_word_range(verse_text, start_idx, start_idx + len(red_words) - 1, verse_words)

    # Fallback: if >60% of red words found sequentially, mark the whole verse
    if len(red_words) > 3:
        match_count = sum(1 for w in red_words if w in verse_words)
        if match_count > len(red_words) * 0.6:
            return wrap_entire_verse(verse_text)

    return None


def find_word_sequence(haystack, needle):
    """Find the starting index of needle words within haystack words."""
    if len(needle) > len(haystack):
        return None
    # Look for first word match and verify sequence
    first_word = needle[0]
    for i in range(len(haystack) - len(needle) + 1):
        if haystack[i] == first_word:
            # Check if enough words match (allow some fuzzy matching)
            matches = 0
            for j, nw in enumerate(needle):
                if i + j < len(haystack) and haystack[i + j] == nw:
                    matches += 1
            # Accept if 80%+ match
            if matches >= len(needle) * 0.8:
                return i
    return None


def wrap_entire_verse(verse_text):
    """Wrap the entire verse text in <r>...</r>, preserving [Psalm title] outside."""
    # Extract [Psalm title] prefix if present
    psalm_match = re.match(r'^(\[.+?\]\s*)', verse_text)
    if psalm_match:
        prefix = psalm_match.group(1)
        rest = verse_text[len(prefix):]
        return prefix + '<r>' + rest + '</r>'
    return '<r>' + verse_text + '</r>'


def wrap_word_range(verse_text, start_word_idx, end_word_idx, plain_words):
    """
    Wrap a range of words in verse_text with <r>...</r>.

    Maps word indices from plain text back to positions in the original verse_text
    (which contains {footnote} and <i> markers).
    """
    # This is complex because we need to map word positions in plain text
    # back to character positions in the marked-up verse text.

    # Strategy: walk through verse_text character by character,
    # tracking which plain-text word we're at, and insert <r>/<r> at the right spots.

    result = []
    word_idx = 0
    i = 0
    in_marker = False  # inside {footnote} or <i>...</i>
    marker_type = None
    red_started = False
    current_word = []

    while i < len(verse_text):
        ch = verse_text[i]

        # Handle [Psalm title] at start
        if i == 0 and ch == '[':
            bracket_end = verse_text.find(']', i)
            if bracket_end > 0:
                # Skip past psalm title and any trailing space
                title_end = bracket_end + 1
                while title_end < len(verse_text) and verse_text[title_end] == ' ':
                    title_end += 1
                result.append(verse_text[:title_end])
                i = title_end
                continue

        # Handle {footnote markers}
        if ch == '{':
            brace_end = verse_text.find('}', i)
            if brace_end > 0:
                marker = verse_text[i:brace_end + 1]
                # If we're in the red zone, include footnote inside <r>
                if red_started:
                    result.append(marker)
                else:
                    result.append(marker)
                i = brace_end + 1
                continue

        # Handle <i>...</i> markers
        if ch == '<' and verse_text[i:i+3] == '<i>':
            end_tag = verse_text.find('</i>', i)
            if end_tag > 0:
                marker = verse_text[i:end_tag + 4]
                result.append(marker)
                # Count words inside italic
                inner = verse_text[i+3:end_tag]
                inner_words = inner.split()
                for w in inner_words:
                    if word_idx == start_word_idx and not red_started:
                        # Need to insert <r> before this italic block
                        # Back up and insert
                        result.insert(-1, '<r>')
                        red_started = True
                    word_idx += 1
                    if word_idx > end_word_idx and red_started:
                        result.append('</r>')
                        red_started = False
                i = end_tag + 4
                continue

        # Handle existing <r>...</r> markers (if re-running)
        if ch == '<' and verse_text[i:i+3] == '<r>':
            end_tag = verse_text.find('</r>', i)
            if end_tag > 0:
                # Strip existing markers
                inner = verse_text[i+3:end_tag]
                result.append(inner)
                i = end_tag + 4
                continue

        # Regular text
        if ch.isspace():
            if current_word:
                # End of a word
                word_text = ''.join(current_word)
                if word_idx == start_word_idx and not red_started:
                    result.append('<r>')
                    red_started = True
                result.append(word_text)
                word_idx += 1
                if word_idx > end_word_idx and red_started:
                    result.append('</r>')
                    red_started = False
                current_word = []
            result.append(ch)
        else:
            current_word.append(ch)

        i += 1

    # Flush last word
    if current_word:
        word_text = ''.join(current_word)
        if word_idx == start_word_idx and not red_started:
            result.append('<r>')
            red_started = True
        result.append(word_text)
        word_idx += 1
        if word_idx > end_word_idx and red_started:
            result.append('</r>')
            red_started = False

    # Close any unclosed <r> tag
    if red_started:
        result.append('</r>')

    return ''.join(result)


def apply_red_letter_to_kjv(kjv_data, red_map, dry_run=False):
    """
    Apply red letter markers to kjv.json data.

    Args:
        kjv_data: Parsed kjv.json (list of book objects)
        red_map: {(book, chapter, verse) → red_text} from CrossWire
        dry_run: If True, don't modify data, just report

    Returns:
        (modified_kjv_data, stats_dict)
    """
    # Build book name → kjv_data index mapping
    book_index = {}
    for i, book in enumerate(kjv_data):
        book_index[book['abbrev']] = i

    stats = {
        'total_red_verses': len(red_map),
        'matched': 0,
        'full_verse_red': 0,
        'partial_verse_red': 0,
        'failed': 0,
        'failed_verses': [],
        'books_affected': set(),
    }

    for (osis_book, chapter, verse_num), red_text in sorted(red_map.items()):
        # Map OSIS book name to kjv.json abbreviation
        kjv_abbrev = OSIS_TO_KJV.get(osis_book)
        if not kjv_abbrev or kjv_abbrev not in book_index:
            stats['failed'] += 1
            stats['failed_verses'].append(f"{osis_book} {chapter}:{verse_num} (unknown book)")
            continue

        book_idx = book_index[kjv_abbrev]
        book = kjv_data[book_idx]

        # kjv.json chapters are 0-indexed
        ch_idx = chapter - 1

        if ch_idx >= len(book['chapters']):
            stats['failed'] += 1
            stats['failed_verses'].append(f"{osis_book} {chapter}:{verse_num} (chapter out of range)")
            continue

        # Try the exact verse first, then adjacent verses (±1, ±2, ±3)
        # This handles verse numbering differences between CrossWire and kjv.json
        vs_candidates = [verse_num - 1]  # 0-indexed exact match
        for offset in [-1, 1, -2, 2, -3, 3]:
            candidate = verse_num - 1 + offset
            if 0 <= candidate < len(book['chapters'][ch_idx]):
                vs_candidates.append(candidate)

        matched = False
        for vs_idx in vs_candidates:
            if vs_idx < 0 or vs_idx >= len(book['chapters'][ch_idx]):
                continue

            verse_text = book['chapters'][ch_idx][vs_idx]
            plain_text = get_kjv_plain_text(verse_text)
            plain_norm = normalize_for_matching(plain_text)
            red_norm = normalize_for_matching(red_text)

            # Try to apply red letter markers
            result = find_red_text_boundaries(verse_text, red_text)

            if result is not None:
                if not dry_run:
                    kjv_data[book_idx]['chapters'][ch_idx][vs_idx] = result
                stats['matched'] += 1
                stats['books_affected'].add(kjv_abbrev)

                # Determine if full or partial
                if red_norm == plain_norm or len(red_norm) > len(plain_norm) * 0.85:
                    stats['full_verse_red'] += 1
                else:
                    stats['partial_verse_red'] += 1

                if vs_idx != verse_num - 1:
                    stats.setdefault('shifted_verses', []).append(
                        f"{osis_book} {chapter}:{verse_num} → verse {vs_idx + 1}")
                matched = True
                break

        if not matched:
            stats['failed'] += 1
            # Show the exact verse text for debugging
            vs_idx = verse_num - 1
            if 0 <= vs_idx < len(book['chapters'][ch_idx]):
                plain_text = get_kjv_plain_text(book['chapters'][ch_idx][vs_idx])
            else:
                plain_text = "(out of range)"
            stats['failed_verses'].append(
                f"{osis_book} {chapter}:{verse_num} (match failed: "
                f"red='{red_text[:50]}...' verse='{plain_text[:50]}...')"
            )

    stats['books_affected'] = sorted(stats['books_affected'])
    return kjv_data, stats


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Add red letter markers to kjv.json')
    parser.add_argument('--xml', default='/tmp/kjvfull.xml',
                        help='Path to CrossWire OSIS XML file')
    parser.add_argument('--kjv', default=None,
                        help='Path to kjv.json (default: auto-detect)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would change without modifying files')
    args = parser.parse_args()

    # Find kjv.json
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    kjv_path = args.kjv or os.path.join(script_dir, 'data', 'kjv.json')

    if not os.path.exists(args.xml):
        print(f"ERROR: CrossWire XML not found: {args.xml}")
        print("Download it with:")
        print("  curl -o /tmp/kjvfull.xml https://gitlab.com/crosswire-bible-society/kjv/-/raw/master/kjvfull.xml")
        sys.exit(1)

    if not os.path.exists(kjv_path):
        print(f"ERROR: kjv.json not found: {kjv_path}")
        sys.exit(1)

    # Step 1: Extract red letter map from CrossWire XML
    red_map = extract_red_letter_map(args.xml)
    print(f"\nExtracted {len(red_map)} verses with words of Christ")

    # Show book distribution
    book_counts = defaultdict(int)
    for (book, ch, vs) in red_map:
        book_counts[book] += 1
    print("\nVerses by book:")
    for book, count in sorted(book_counts.items(), key=lambda x: -x[1]):
        print(f"  {book}: {count}")

    # Step 2: Load kjv.json
    print(f"\nLoading {kjv_path}...")
    with open(kjv_path, 'r', encoding='utf-8') as f:
        kjv_data = json.load(f)

    # Strip any existing <r> markers (for idempotent re-runs)
    for book in kjv_data:
        for ch_idx, chapter in enumerate(book['chapters']):
            for vs_idx, verse in enumerate(chapter):
                if '<r>' in verse:
                    book['chapters'][ch_idx][vs_idx] = re.sub(r'<r>(.*?)</r>', r'\1', verse)

    # Step 3: Apply red letter markers
    print(f"\n{'DRY RUN: ' if args.dry_run else ''}Applying red letter markers...")
    kjv_data, stats = apply_red_letter_to_kjv(kjv_data, red_map, dry_run=args.dry_run)

    # Step 4: Report
    print(f"\n{'=' * 50}")
    print(f"RED LETTER RESULTS")
    print(f"{'=' * 50}")
    print(f"Total verses with Christ's words: {stats['total_red_verses']}")
    print(f"Successfully marked:              {stats['matched']}")
    print(f"  Full verse red:                 {stats['full_verse_red']}")
    print(f"  Partial verse red:              {stats['partial_verse_red']}")
    print(f"Failed to match:                  {stats['failed']}")
    print(f"Books affected:                   {', '.join(stats['books_affected'])}")

    shifted = stats.get('shifted_verses', [])
    if shifted:
        print(f"\nShifted verses (matched via adjacent verse, {len(shifted)} total):")
        for v in shifted[:10]:
            print(f"  - {v}")
        if len(shifted) > 10:
            print(f"  ... and {len(shifted) - 10} more")

    if stats['failed_verses']:
        print(f"\nFailed verses ({len(stats['failed_verses'])}):")
        for v in stats['failed_verses'][:20]:
            print(f"  - {v}")
        if len(stats['failed_verses']) > 20:
            print(f"  ... and {len(stats['failed_verses']) - 20} more")

    # Step 5: Write updated kjv.json
    if not args.dry_run and stats['matched'] > 0:
        print(f"\nWriting updated {kjv_path}...")
        with open(kjv_path, 'w', encoding='utf-8') as f:
            json.dump(kjv_data, f, ensure_ascii=False)
        print(f"Done! {stats['matched']} verses marked with red letter text.")
    elif args.dry_run:
        print(f"\nDry run complete. No files modified.")
    else:
        print(f"\nNo verses matched. kjv.json unchanged.")

    # Sample verification
    if stats['matched'] > 0:
        print(f"\nSample marked verses:")
        samples = [('Matt', 4, 19), ('John', 3, 16), ('Matt', 5, 3), ('Rev', 1, 8)]
        for book_name, ch, vs in samples:
            abbrev = OSIS_TO_KJV.get(book_name, book_name)
            for book in kjv_data:
                if book['abbrev'] == abbrev:
                    if ch - 1 < len(book['chapters']) and vs - 1 < len(book['chapters'][ch - 1]):
                        text = book['chapters'][ch - 1][vs - 1]
                        if '<r>' in text:
                            # Show abbreviated
                            display = text[:120] + ('...' if len(text) > 120 else '')
                            print(f"  {book_name} {ch}:{vs}: {display}")
                    break

    return 0 if stats['failed'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
