#!/usr/bin/env python3
"""Generate glossary-index.json -- a paragraph-precise locator file for the glossary,
modeled on the topical index (index-data/topical-index.json).

Each glossary entry in appendix-r-glossary.md ends with hand-authored pointers like
"See Chapter 15 and Appendix A1." This script turns each such Chapter/Appendix pointer
into a {phrase, section} locator: it opens the referenced source section, finds where
the glossary headword (or its core words) is actually discussed, and captures a short
verbatim phrase there. At book-build time the PDF resolves each phrase to the exact
page (same resolver the topical index uses), so the glossary can print the precise
page of the discussion instead of the chapter's opening page.

Output: index-data/glossary-index.json (list of {term, locations:[{phrase, section}]}).
A locator with phrase=null means the headword wasn't found in that section; the build
falls back to the section's opening page for those.

Usage: python3 scripts/build_glossary_index.py [SOURCE_DIR]
"""
import json, os, re, sys, glob

SRC = sys.argv[1] if len(sys.argv) > 1 else os.environ.get(
    "BOOK_SOURCE_DIR", os.path.expanduser("~/Anna/Mind"))
GLOSSARY = os.path.join(SRC, "appendix-r-glossary.md")
OUT_DIR = os.path.join(SRC, "index-data")
OUT = os.path.join(OUT_DIR, "glossary-index.json")
OUT_RAW = os.path.join(OUT_DIR, "glossary-index.raw.json")

# ---- source-file maps -------------------------------------------------------
def _section_files():
    ch, app = {}, {}
    for p in glob.glob(os.path.join(SRC, "chapter-*.md")):
        m = re.match(r'chapter-0*(\d+)-', os.path.basename(p))
        if m:
            ch[int(m.group(1))] = p
    for p in glob.glob(os.path.join(SRC, "appendix-*.md")):
        m = re.match(r'appendix-([a-z]\d*)-', os.path.basename(p))
        if m:
            app[m.group(1).upper()] = p
    return ch, app

CH_FILES, APP_FILES = _section_files()

# ---- text cleaning ----------------------------------------------------------
def clean(md):
    """Strip frontmatter + markdown noise so phrases match rendered prose."""
    md = re.sub(r'^---\n.*?\n---\n', '', md, flags=re.S)         # frontmatter
    md = re.sub(r'<[^>]+>', ' ', md)                            # raw HTML tags
    md = re.sub(r'\[\^[^\]]+\]:?', '', md)                      # footnote markers/defs
    md = re.sub(r'!?\[([^\]]*)\]\([^)]*\)', r'\1', md)          # links/images -> text
    md = re.sub(r'[*_`#>]', '', md)                             # emphasis/heading/quote marks
    md = re.sub(r'\s+', ' ', md)
    return md.strip()

def section_text(label):
    """Return cleaned prose for 'Chapter N' / 'Appendix X', or None."""
    m = re.match(r'Chapter (\d+)', label)
    if m:
        p = CH_FILES.get(int(m.group(1)))
    else:
        m = re.match(r'Appendix ([A-Za-z]\d*)', label)
        p = APP_FILES.get(m.group(1).upper()) if m else None
    if not p or not os.path.exists(p):
        return None
    return clean(open(p, encoding="utf-8").read())

# ---- headword -> search candidates ------------------------------------------
def candidates(headword):
    """Ordered search strings, most specific first."""
    h = headword.strip()
    base = re.sub(r'\s*\(.*?\)', '', h).strip()                 # drop "(qualifier)"
    cands = []
    for c in (h, base):
        if c and c not in cands:
            cands.append(c)
    # also a slash/comma alias ("Jehovah / YHWH" -> "Jehovah", "YHWH")
    for part in re.split(r'\s*[/,]\s*', base):
        part = part.strip()
        if len(part) > 3 and part not in cands:
            cands.append(part)
    return cands

WORDS = 12  # phrase length captured at the match
def find_phrase(text, headword):
    """First verbatim phrase in `text` containing the headword (or a core form)."""
    low = text.lower()
    for cand in candidates(headword):
        i = low.find(cand.lower())
        if i < 0:
            continue
        # back up to a word boundary, then take ~WORDS words from there
        start = i
        window = text[start:start + 400]
        phrase = " ".join(window.split()[:WORDS]).strip(" ,;:.")
        if len(phrase) >= 12:
            return phrase
    return None

# ---- parse glossary entries -------------------------------------------------
def parse_entries():
    md = re.sub(r'^---\n.*?\n---\n', '', open(GLOSSARY, encoding="utf-8").read(), flags=re.S)
    entries = []
    for m in re.finditer(r'\*\*(.+?)\.\*\*(.*?)(?=\n\*\*|\Z)', md, flags=re.S):
        head = m.group(1).strip()
        body = m.group(2)
        secs = []
        # chapter refs: "Chapter 15", "Chapters 1, 5, and 12"
        for run in re.finditer(r'Chapters?\s+(\d+(?:\s*,\s*\d+)*(?:\s*,?\s+and\s+\d+)?)', body):
            for n in re.findall(r'\d+', run.group(1)):
                lab = f"Chapter {n}"
                if lab not in secs:
                    secs.append(lab)
        # appendix refs: "Appendix A1", "Appendices H and J"
        for run in re.finditer(r'Appendi(?:x|ces)\s+((?:A\d+|[A-Z](?![a-z]))(?:\s*,\s*(?:A\d+|[A-Z](?![a-z])))*(?:\s*,?\s+and\s+(?:A\d+|[A-Z](?![a-z])))?)', body):
            for k in re.findall(r'A\d+|[A-Z]', run.group(1)):
                lab = f"Appendix {k}"
                if lab not in secs:
                    secs.append(lab)
        entries.append((head, secs))
    return entries

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    entries = parse_entries()
    out = []
    cache = {}
    found = missing = 0
    for head, secs in entries:
        locs = []
        for lab in secs:
            if lab not in cache:
                cache[lab] = section_text(lab)
            txt = cache[lab]
            phrase = find_phrase(txt, head) if txt else None
            locs.append({"phrase": phrase, "section": lab})
            if phrase:
                found += 1
            else:
                missing += 1
        if locs:
            out.append({"term": head, "locations": locs})
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(out, open(OUT_RAW, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"glossary terms: {len(out)}")
    print(f"locators: {found + missing}  resolved-phrase: {found}  fallback(section-start): {missing}")
    print(f"wrote {OUT}")

if __name__ == "__main__":
    main()
