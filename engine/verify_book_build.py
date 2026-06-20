#!/usr/bin/env python3
"""Comprehensive post-build verification for every book edition.

Checks, per edition:
  PDFs (web-pdf, 7x10, 6x9, 8.5x11):
    1. Index precision: 0 out-of-section locators; section-start <= small tolerance.
    2. Glossary link<->number agreement: each printed "(p. N)" has a glx link landing
       on the same page (label space).
    3. No dead internal links: every named destination referenced by a link annotation
       exists (sample TOC + cross-ref + index links).
    4. web-pdf only: PageLabels present (cover labeled, content starts at "1").
  EPUB:
    5. Every #glx-* / #ix-* link in the glossary/topical index resolves to an id that
       exists in the target content file.

Exit 0 if all PASS, 1 otherwise. Prints a PASS/FAIL line per check.
"""
import os
import re
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import index_anchors
import classify_index_anchors as C

HOME = os.path.expanduser('~')
B = os.path.join(HOME, 'Anna', 'Mind')
PDFS = {
    'web-pdf': os.path.join(B, 'A-Thought-in-the-Mind-of-God.pdf'),
    '7x10': os.path.join(B, 'ingramspark', 'A-Thought-in-the-Mind-of-God-7x10.pdf'),
    '6x9': os.path.join(B, 'ingramspark', 'A-Thought-in-the-Mind-of-God-6x9.pdf'),
    '8.5x11': os.path.join(B, 'ingramspark', 'A-Thought-in-the-Mind-of-God-8.5x11-hardcover.pdf'),
}
EPUB = os.path.join(B, 'A-Thought-in-the-Mind-of-God.epub')

results = []
def check(name, ok, detail=''):
    results.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}{(' -- ' + detail) if detail else ''}")


def verify_pdf(label, path):
    from pypdf import PdfReader
    print(f"\n=== {label}: {os.path.basename(path)} ===")
    if not os.path.exists(path):
        check(f"{label} exists", False, "missing"); return
    reader = PdfReader(path)
    # PageLabel-aware page numbers (web-PDF cover doesn't shift the content numbering).
    pages = C.build_page_cache(path)
    bm = C.find_backmatter_start(pages)
    starts, ranges, cap = C.build_section_ranges(pages, bm)
    norm_pages = [(p, index_anchors._norm(t)) for p, t in pages]
    classify = C.make_classifier(norm_pages, ranges)

    # 1. index precision
    import json
    for idxlabel, jpath in [('glossary', C.GLOSSARY_JSON), ('topical', C.TOPICAL_JSON)]:
        entries = json.load(open(jpath, encoding='utf-8'))
        out = start = 0
        for e in entries:
            for loc in e.get('locations', []):
                b = classify(loc.get('phrase', ''), loc.get('section', ''))
                if b == 'out_of_section':
                    out += 1
                elif b == 'section_start':
                    start += 1
        check(f"{label} {idxlabel} 0 out-of-section", out == 0, f"out={out} start={start}")
        check(f"{label} {idxlabel} section-start <=3", start <= 3, f"start={start}")

    # page labels (web-pdf)
    try:
        pl = reader.page_labels
    except Exception:
        pl = [str(i + 1) for i in range(len(pages))]
    if label == 'web-pdf':
        ok = pl[0] == 'Cover' and pl[1] == '1'
        check("web-pdf PageLabels (cover + content@1)", ok, f"[0]={pl[0]!r} [1]={pl[1]!r}")

    # 2. glossary link <-> number agreement
    nd = reader.named_destinations
    def labelof(nm):
        d = nd.get(nm)
        if not d:
            return None
        try:
            pn = reader.get_destination_page_number(d)
            return pl[pn] if pn is not None else None
        except Exception:
            return None
    gstart = next((i for i, (p, t) in enumerate(pages) if t.lstrip().startswith('Glossary')), None)
    tot = match = 0
    if gstart is not None:
        for i in range(gstart, len(pages)):
            t = pages[i][1]
            if t.lstrip().startswith('Bibliography') or t.lstrip().startswith('Notes'):
                break
            printed = re.findall(r'\(p\. (\d+)\)', t)
            if not printed:
                continue
            landings = set()
            for a in (reader.pages[i].get('/Annots') or []):
                ds = str((a.get_object().get('/A', {})).get('/D') or a.get_object().get('/Dest') or '')
                mm = re.search(r'(glx-\d+)', ds)
                if mm:
                    landings.add(labelof(mm.group(1)))
            tot += len(printed)
            match += sum(1 for x in printed if x in landings)
    pct = round(100 * match / tot) if tot else 0
    check(f"{label} glossary link==number >=90%", pct >= 90, f"{match}/{tot} ({pct}%)")

    # 3. dead internal links: sample link annotations, named-dest targets must exist
    dead = 0
    seen = 0
    for pg in reader.pages:
        for a in (pg.get('/Annots') or []):
            obj = a.get_object()
            A = obj.get('/A', {})
            dest = A.get('/D') or obj.get('/Dest')
            if dest is None:
                continue
            if isinstance(dest, str):
                seen += 1
                if dest not in nd:
                    dead += 1
        if seen > 4000:
            break
    check(f"{label} no dead named-dest links", dead == 0, f"dead={dead}/{seen}")


def verify_epub():
    print(f"\n=== EPUB: {os.path.basename(EPUB)} ===")
    if not os.path.exists(EPUB):
        check("EPUB exists", False, "missing"); return
    z = zipfile.ZipFile(EPUB)
    names = [n for n in z.namelist() if n.endswith('.xhtml')]
    # collect all ids per file
    ids_by_file = {}
    for n in names:
        html = z.read(n).decode('utf-8', 'ignore')
        ids_by_file[os.path.basename(n)] = set(re.findall(r'id="([^"]+)"', html))
    # for each glx/ix link, the target file#id must exist
    bad_glx = bad_ix = tot_glx = tot_ix = 0
    for n in names:
        html = z.read(n).decode('utf-8', 'ignore')
        for m in re.finditer(r'href="([^"#]+)#((?:glx|ix)-[^"]+)"', html):
            tgt_file, anc = os.path.basename(m.group(1)), m.group(2)
            ok = anc in ids_by_file.get(tgt_file, set())
            if anc.startswith('glx-'):
                tot_glx += 1; bad_glx += (0 if ok else 1)
            else:
                tot_ix += 1; bad_ix += (0 if ok else 1)
    check("EPUB glossary #glx links resolve", bad_glx == 0 and tot_glx > 0, f"bad={bad_glx}/{tot_glx}")
    check("EPUB topical #ix links resolve", bad_ix == 0 and tot_ix > 0, f"bad={bad_ix}/{tot_ix}")


if __name__ == '__main__':
    for label, path in PDFS.items():
        verify_pdf(label, path)
    verify_epub()
    print(f"\n{'='*50}")
    npass = sum(results); ntot = len(results)
    print(f"RESULT: {npass}/{ntot} checks passed")
    sys.exit(0 if npass == ntot else 1)
