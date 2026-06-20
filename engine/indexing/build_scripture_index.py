#!/usr/bin/env python3
"""
Generate Scripture Index for "A Thought in the Mind of God"
Scans all chapters and appendices for scripture references and builds the index.
"""

import re
import os
import sys
from collections import defaultdict

BOOK_DIR = os.path.dirname(os.path.abspath(__file__))

# Bible book names and abbreviations
BIBLE_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
    "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
    "Ezra", "Nehemiah", "Esther", "Job", "Psalm", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
    "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
    "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
    "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts",
    "Romans", "1 Corinthians", "2 Corinthians", "Galatians",
    "Ephesians", "Philippians", "Colossians",
    "1 Thessalonians", "2 Thessalonians",
    "1 Timothy", "2 Timothy", "Titus", "Philemon",
    "Hebrews", "James", "1 Peter", "2 Peter",
    "1 John", "2 John", "3 John", "Jude", "Revelation"
]

# Canonical sort order
BOOK_ORDER = {book: i for i, book in enumerate(BIBLE_BOOKS)}
# Normalize Psalms -> Psalm
BOOK_ORDER["Psalms"] = BOOK_ORDER["Psalm"]

def get_chapter_label(filename):
    """Extract a human-readable label from filename."""
    base = os.path.basename(filename)
    if base.startswith("chapter-"):
        # chapter-01-the-sentence.md -> Ch. 1
        match = re.match(r'chapter-(\d+)', base)
        if match:
            return f"Ch. {int(match.group(1))}"
    elif base.startswith("appendix-"):
        # appendix-a-the-sentence-applied.md -> App. A
        # appendix-a7-personal-ethics.md    -> App. A7
        match = re.match(r'appendix-([a-z])(\d+)?', base)
        if match:
            letter = match.group(1).upper()
            num = match.group(2)
            return f"App. {letter}{num}" if num else f"App. {letter}"
    elif "prologue" in base:
        return "Prologue"
    elif "preface" in base:
        return "Preface"
    elif "epilogue" in base:
        return "Epilogue"
    return base

def parse_reference(ref_str):
    """Parse a scripture reference string into (book, chapter, verse_range)."""
    # Normalize
    ref_str = ref_str.strip()
    # Match: Book Chapter:Verse(-Verse)
    match = re.match(r'^(.+?)\s+(\d+):(\d+(?:-\d+)?)$', ref_str)
    if match:
        return (match.group(1), int(match.group(2)), match.group(3))
    # Match: Book Chapter (no verse)
    match = re.match(r'^(.+?)\s+(\d+)$', ref_str)
    if match:
        return (match.group(1), int(match.group(2)), None)
    return None

def normalize_book(book):
    """Normalize book name."""
    if book == "Psalms":
        return "Psalm"
    return book

# Abbreviated book forms used in the body (dense cross-reference lists/tables cite
# in abbreviated form: "Rom. 8:30", "1 Cor. 13:1", "Ps. 23:1"). Each maps to the
# canonical full name so abbreviated and full citations dedupe to one index entry.
ABBREV = {
    "Gen": "Genesis", "Ex": "Exodus", "Exod": "Exodus", "Lev": "Leviticus",
    "Num": "Numbers", "Deut": "Deuteronomy", "Josh": "Joshua", "Judg": "Judges",
    "1 Sam": "1 Samuel", "2 Sam": "2 Samuel", "1 Ki": "1 Kings", "2 Ki": "2 Kings",
    "1 Kgs": "1 Kings", "2 Kgs": "2 Kings", "1 Chron": "1 Chronicles",
    "2 Chron": "2 Chronicles", "Neh": "Nehemiah", "Esth": "Esther",
    "Ps": "Psalm", "Pss": "Psalm", "Prov": "Proverbs", "Eccl": "Ecclesiastes",
    "Isa": "Isaiah", "Jer": "Jeremiah", "Lam": "Lamentations", "Ezek": "Ezekiel",
    "Dan": "Daniel", "Hos": "Hosea", "Obad": "Obadiah", "Mic": "Micah",
    "Nah": "Nahum", "Hab": "Habakkuk", "Zeph": "Zephaniah", "Hag": "Haggai",
    "Zech": "Zechariah", "Mal": "Malachi", "Matt": "Matthew", "Rom": "Romans",
    "1 Cor": "1 Corinthians", "2 Cor": "2 Corinthians", "Gal": "Galatians",
    "Eph": "Ephesians", "Phil": "Philippians", "Col": "Colossians",
    "1 Thess": "1 Thessalonians", "2 Thess": "2 Thessalonians",
    "1 Tim": "1 Timothy", "2 Tim": "2 Timothy", "Tit": "Titus",
    "Philem": "Philemon", "Phlm": "Philemon", "Heb": "Hebrews", "Jas": "James",
    "1 Pet": "1 Peter", "2 Pet": "2 Peter", "Rev": "Revelation",
}

# Map every matchable form (full name + abbreviation) to its canonical full name.
BOOK_FORMS = {b: normalize_book(b) for b in BIBLE_BOOKS}
BOOK_FORMS.update(ABBREV)
# Longest-first so "Philem" wins over "Phil", "1 Corinthians" over "1 Cor", etc.
# An optional "." may follow an abbreviation. Captures (form, chapter:verse[-verse]).
_BOOK_REF_RE = re.compile(
    r'\b(' + '|'.join(re.escape(f) for f in sorted(BOOK_FORMS, key=len, reverse=True))
    + r')\.?\s+(\d+:\d+(?:-\d+)?)')

def sort_key(ref_str):
    """Sort key for a scripture reference."""
    parsed = parse_reference(ref_str)
    if not parsed:
        return (999, 0, 0)
    book, chapter, verse = parsed
    book = normalize_book(book)
    book_idx = BOOK_ORDER.get(book, 999)
    verse_num = 0
    if verse:
        verse_num = int(verse.split('-')[0])
    return (book_idx, chapter, verse_num)

def scan_file(filepath):
    """Scan a markdown file for scripture references (full names + abbreviations).

    'For Further Study' sections are EXCLUDED: those are curated suggested-reading
    lists, not places Scripture is quoted, discussed, or marshaled as evidence, so
    they don't belong in the Scripture Index (decision 2026-06-08, option B).
    """
    refs = set()
    with open(filepath, encoding='utf-8') as f:
        content = f.read()

    # Drop For Further Study lists -- two forms in this book, both suggested-reading:
    #   chapters: a "## For Further Study" HEADING section (to the next heading/EOF)
    #   applied appendices (A1-A12): an inline "**For further study:** v; v; v." paragraph
    content = re.sub(r'(?ims)^##\s*For Further Study\b.*?(?=^\#{1,6}\s|\Z)', '', content)
    content = re.sub(r'(?is)\*\*For further study:?\*\*.*?(?=\n\n|\Z)', '', content)

    # Match full names AND abbreviations; normalize the book to its canonical full
    # name so "Rom. 8:30" and "Romans 8:30" collapse to one entry.
    for m in _BOOK_REF_RE.finditer(content):
        full = BOOK_FORMS[m.group(1)]
        refs.add(f"{full} {m.group(2)}")

    return refs

def main():
    # Find all content files
    files = []
    for f in sorted(os.listdir(BOOK_DIR)):
        if f.startswith("chapter-") and f.endswith(".md"):
            files.append(os.path.join(BOOK_DIR, f))
        elif (f.startswith("appendix-") and f.endswith(".md")
              # Skip the reference apparatus -- a Scripture Index should point into
              # the content (chapters + content appendices), not circularly into the
              # other back matter (topical index, glossary, bibliography).
              and not any(s in f for s in ("scripture-index", "topical-index", "glossary", "bibliography"))):
            files.append(os.path.join(BOOK_DIR, f))

    # Also scan prologue, preface, epilogue
    for f in ["prologue.md", "preface.md", "epilogue.md"]:
        path = os.path.join(BOOK_DIR, f)
        if os.path.exists(path):
            files.append(path)

    # Scan all files
    # ref_str -> set of chapter labels
    index = defaultdict(set)

    for filepath in files:
        label = get_chapter_label(filepath)
        refs = scan_file(filepath)
        for ref in refs:
            index[ref].add(label)

    # Sort references by Bible book order
    sorted_refs = sorted(index.keys(), key=sort_key)

    # Generate markdown
    lines = []
    lines.append('---')
    lines.append('title: "Scripture Index"')
    lines.append('status: generated')
    lines.append('---')
    lines.append('')
    lines.append('# Scripture Index')
    lines.append('')
    lines.append('All Scripture quotations are from the King James Version (KJV). References are listed by book, chapter, and verse, with the chapter(s) or appendix where each passage appears.')
    lines.append('')

    current_book = None
    for ref in sorted_refs:
        parsed = parse_reference(ref)
        if parsed:
            book = normalize_book(parsed[0])
            if book != current_book:
                if current_book is not None:
                    lines.append('')
                lines.append(f'**{book}**')
                lines.append('')
                current_book = book

        # Sort chapter labels
        labels = sorted(index[ref], key=lambda x: (
            0 if x.startswith("Ch.") else 1 if x.startswith("App.") else 2,
            int(x.split()[-1]) if x.startswith("Ch.") else x
        ))
        label_str = ', '.join(labels)
        lines.append(f'- {ref} - {label_str}')

    # Write the index
    output_path = os.path.join(BOOK_DIR, "appendix-p-scripture-index.md")
    with open(output_path, 'w') as f:
        f.write('\n'.join(lines) + '\n')

    print(f"Generated scripture index: {len(sorted_refs)} references from {len(files)} files")

if __name__ == "__main__":
    main()
