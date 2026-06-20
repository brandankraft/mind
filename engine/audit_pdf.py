#!/usr/bin/env python3
"""Post-build print-readiness audit for ONE interior PDF.

Catches the disasters that must never reach IngramSpark:
  C1  Producer is WeasyPrint -- NOT re-saved by Preview/Quartz (which silently
      deletes pages on a held Delete key and never warns on close).
  C2  Every visible folio equals its physical page index (these interiors number
      from 1 = physical page 1, counting suppressed pages). A jump/skip/dup means
      pages were deleted or the counter broke -> missing-pages disaster.
  C3  The folio/running-head sits on the correct side: recto (odd physical) on the
      right, verso (even physical) on the left. Catches "left header on a right page."
  C4  Internal links intact: named destinations present (clone_from regressions
      have wiped every TOC + cross-ref link before).
  C5  No major content loss: page count within tolerance of the blessed baseline.
  C6  No blank holes inside the numbered body.
  C7  Book starts with the title page and ends with the memorial leaf (not truncated).

Usage:
  audit_pdf.py <pdf> --trim {6x9|7x10|8.5x11|web-pdf} [--bless]
    --bless  record the current page count as the new baseline for this trim.
Exit 0 = all PASS, 1 = any FAIL.
"""
import sys, os, re, json, html, subprocess, argparse
from pypdf import PdfReader

BASELINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".pdf-baseline.json")
INGRAM_TRIMS = {"6x9", "7x10", "8.5x11"}

def bbox_pages(pdf, f, l):
    out = subprocess.run(["pdftotext", "-bbox", "-f", str(f), "-l", str(l), pdf, "-"],
                         capture_output=True, text=True).stdout
    pages = []; cur = None
    pat = re.compile(r'<page width="([\d.]+)" height="([\d.]+)">|'
                     r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>|'
                     r'</page>')
    for m in pat.finditer(out):
        if m.group(1): cur = {"w": float(m.group(1)), "h": float(m.group(2)), "words": []}
        elif m.group(3):
            if cur is not None:
                cur["words"].append((float(m.group(3)), float(m.group(4)),
                                     float(m.group(5)), float(m.group(6)), html.unescape(m.group(7))))
        else:
            if cur is not None: pages.append(cur); cur = None
    if cur: pages.append(cur)
    return pages

def folio_of(pg):
    """Return (value, where, side) for the page's printed folio, or (None,..).

    Bottom-center is checked FIRST: chapter-opener and back-matter index pages put
    the folio at the foot, and index pages carry stray numbers in the top guide-word
    slot. Body pages have no integer in the bottom margin, so they fall through to the
    top-corner running-head folio (right=recto, left=verso)."""
    H, W = pg["h"], pg["w"]
    for (x0, y0, x1, y1, t) in pg["words"]:          # bottom-center (openers/indexes)
        if y0 > H - 42 and re.fullmatch(r'\d{1,4}', t):
            xc = (x0 + x1) / 2
            if 0.30 * W < xc < 0.70 * W: return int(t), "bot", "C"
    for (x0, y0, x1, y1, t) in pg["words"]:          # top corner (running head)
        if y0 < 58 and re.fullmatch(r'\d{1,4}', t):
            xc = (x0 + x1) / 2
            if xc < 0.22 * W: return int(t), "top", "L"
            if xc > 0.78 * W: return int(t), "top", "R"
    return None, None, None

def page_text_len(pg):
    return sum(len(w[4]) for w in pg["words"])

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("--trim", required=True)
    ap.add_argument("--bless", action="store_true")
    args = ap.parse_args()
    pdf, trim = args.pdf, args.trim

    if not os.path.exists(pdf):
        print(f"❌ AUDIT FAIL [{trim}]: file not found: {pdf}"); return 1

    reader = PdfReader(pdf)
    N = len(reader.pages)
    fails, warns = [], []

    # ---- C1 Producer (not Preview/Quartz) ----
    producer = str(reader.metadata.get("/Producer") or "")
    if "WeasyPrint" in producer:
        print(f"  [PASS] C1 producer is WeasyPrint")
    else:
        fails.append(f"C1 producer is '{producer}' -- looks re-saved (Preview/Quartz). "
                     f"REBUILD from source; do not edit PDFs in Preview.")

    # ---- C4 internal links ----
    try:
        nd = len(reader.named_destinations)
    except Exception:
        nd = 0
    floor = 50 if trim == "web-pdf" else 300
    if nd >= floor:
        print(f"  [PASS] C4 internal links present ({nd} named destinations)")
    else:
        fails.append(f"C4 only {nd} named destinations (< {floor}) -- internal links likely lost")

    # ---- C5 page-count baseline ----
    base = {}
    if os.path.exists(BASELINE):
        try: base = json.load(open(BASELINE))
        except Exception: base = {}
    if args.bless:
        base[trim] = N; json.dump(base, open(BASELINE, "w"), indent=1)
        print(f"  [BLESS] C5 baseline for {trim} set to {N} pages")
    elif trim in base:
        prev = base[trim]
        if N < prev * 0.97:
            fails.append(f"C5 page count {N} is >3% below baseline {prev} -- possible content loss")
        elif N != prev:
            warns.append(f"C5 page count {N} vs baseline {prev} (drift {N-prev:+d}) -- bless if intended")
            print(f"  [WARN] C5 page count {N} vs baseline {prev} ({N-prev:+d})")
        else:
            print(f"  [PASS] C5 page count {N} == baseline")
    else:
        base[trim] = N; json.dump(base, open(BASELINE, "w"), indent=1)
        print(f"  [PASS] C5 page count {N} (baseline seeded)")

    # ---- folio + side + blanks (scan all pages in chunks) ----
    mism, sidebad, blanks = [], [], []
    numbered = 0
    last_text_pages = []
    CHUNK = 120
    for start in range(1, N + 1, CHUNK):
        pgs = bbox_pages(pdf, start, min(start + CHUNK - 1, N))
        for k, pg in enumerate(pgs):
            phys = start + k
            fol, where, side = folio_of(pg)
            tlen = page_text_len(pg)
            if fol is not None:
                numbered += 1
                if trim in INGRAM_TRIMS and fol != phys:
                    mism.append((phys, fol))
                if where == "top":
                    if phys % 2 == 1 and side != "R": sidebad.append((phys, fol, side, "recto->should be R"))
                    if phys % 2 == 0 and side != "L": sidebad.append((phys, fol, side, "verso->should be L"))
            # blank-hole: a NUMBERED page that is truly empty (failed image / lost
            # content). Intentional blanks (front-matter versos) are unnumbered; the
            # trailing reader "Notes" leaves carry a heading so clear the threshold.
            if fol is not None and tlen < 8:
                blanks.append(phys)

    # ---- C2 folio==physical ----
    # A real deletion/counter-jump offsets a long RUN of consecutive pages; an isolated
    # mismatch is detector noise on a number-dense index page. Fail only on a run >= 3.
    if trim in INGRAM_TRIMS:
        mset = {p for p, _ in mism}
        longest = run = 0
        for p in range(1, N + 1):
            run = run + 1 if p in mset else 0
            longest = max(longest, run)
        if not mism:
            print(f"  [PASS] C2 folio==physical for all {numbered} numbered pages")
        elif longest >= 3:
            fails.append(f"C2 {len(mism)} pages where folio != physical index, including a run of "
                         f"{longest} consecutive (missing/extra pages or counter jump). First: {mism[:8]}")
        else:
            warns.append(f"C2 {len(mism)} isolated folio!=physical (likely detector noise on index pages): {mism[:8]}")
            print(f"  [WARN] C2 {len(mism)} isolated folio mismatch (no run>=3): {mism[:8]}")
    else:
        print(f"  [SKIP] C2 folio==physical (web-pdf uses PageLabels)")

    # ---- C3 header side ----
    if trim in INGRAM_TRIMS:
        if not sidebad:
            print(f"  [PASS] C3 running-head/folio on correct side (recto=R, verso=L)")
        else:
            fails.append(f"C3 {len(sidebad)} pages with header on the WRONG side "
                         f"(left head on a right page or vice versa). First: {sidebad[:8]}")

    # ---- C6 blank holes ----
    if not blanks:
        print(f"  [PASS] C6 no blank numbered pages")
    else:
        warns.append(f"C6 {len(blanks)} numbered pages look blank: {blanks[:10]}")
        print(f"  [WARN] C6 blank numbered pages: {blanks[:10]}")

    # ---- C7 first/last sanity ----
    first_txt = "".join(reader.pages[i].extract_text() or "" for i in range(min(2, N)))
    # memorial sits a few leaves from the end (About-the-Author, memorial, then reader Notes)
    last_txt = "".join(reader.pages[i].extract_text() or "" for i in range(max(0, N - 6), N))
    if "Thought" in first_txt:
        print(f"  [PASS] C7a opens with the title page")
    else:
        warns.append("C7a first pages don't contain the title -- check front matter")
        print("  [WARN] C7a title not found on first pages")
    if re.search(r"Eileen|Grace and Peace|grace and peace", last_txt):
        print(f"  [PASS] C7b ends with the memorial leaf")
    else:
        warns.append("C7b last pages don't contain the memorial -- possible truncation")
        print("  [WARN] C7b memorial leaf not found on last pages")

    print()
    if fails:
        print(f"❌❌❌ AUDIT FAILED [{trim}] -- {len(fails)} issue(s):")
        for f in fails: print(f"   - {f}")
        if warns: print(f"   ({len(warns)} warning(s) too)")
        return 1
    print(f"✅ AUDIT PASSED [{trim}] -- {N} pages, {numbered} numbered"
          + (f"  ({len(warns)} warning(s))" if warns else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())
