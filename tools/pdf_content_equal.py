#!/usr/bin/env python3
"""Compare two PDFs for CONTENT equality, ignoring WeasyPrint's path-derived
image XObject names.

WeasyPrint 68.1 names each embedded image XObject by a hash of its absolute
source path. Building the book from a different absolute directory therefore
changes every image id (and the xref offsets they shift), so the raw bytes
differ even when the rendered book -- pages, text, layout, image pixels -- is
identical. This tool proves content-identity by parsing both PDFs with pypdf:

  1. page count must match,
  2. each page's decompressed content stream must match after canonicalizing
     the /i<32-hex> image ids to sequential tokens (first-appearance order),
  3. the multiset of embedded image data (md5 of each image's raw bytes) must
     match.

Exit 0 => content-identical.  Exit 1 => a real difference (prints what differs).

Usage: pdf_content_equal.py A.pdf B.pdf
"""
import sys, re, hashlib
from pypdf import PdfReader

NAME = re.compile(rb'/i[0-9a-f]{32}')

def canon(b: bytes) -> bytes:
    seen = {}
    def rep(m):
        k = m.group(0)
        if k not in seen:
            seen[k] = ("/iC%d" % len(seen)).encode()
        return seen[k]
    return NAME.sub(rep, b)

def page_streams(reader):
    out = []
    for pg in reader.pages:
        try:
            c = pg.get_contents()
            data = c.get_data() if c is not None else b''
        except Exception:
            data = b''
        out.append(canon(data))
    return out

def image_md5s(reader):
    s = []
    for pg in reader.pages:
        res = pg.get("/Resources") or {}
        xo = res.get("/XObject") or {}
        items = xo.items() if hasattr(xo, "items") else []
        for _name, ref in items:
            o = ref.get_object()
            if o.get("/Subtype") == "/Image":
                try:
                    s.append(hashlib.md5(o.get_data()).hexdigest())
                except Exception:
                    try:
                        s.append(hashlib.md5(o._data).hexdigest())
                    except Exception:
                        s.append("UNREADABLE")
    return sorted(s)

def main():
    a, b = sys.argv[1], sys.argv[2]
    ra, rb = PdfReader(a), PdfReader(b)
    if len(ra.pages) != len(rb.pages):
        print("DIFFERS: page count %d vs %d" % (len(ra.pages), len(rb.pages)))
        return 1
    pa, pb = page_streams(ra), page_streams(rb)
    diff_pages = [i for i, (x, y) in enumerate(zip(pa, pb)) if x != y]
    if diff_pages:
        print("DIFFERS: %d page content streams differ; first pages: %s"
              % (len(diff_pages), diff_pages[:10]))
        return 1
    ia, ib = image_md5s(ra), image_md5s(rb)
    if ia != ib:
        print("DIFFERS: embedded image data differs (%d vs %d images)"
              % (len(ia), len(ib)))
        return 1
    print("CONTENT-IDENTICAL (%d pages, %d images)" % (len(ra.pages), len(ia)))
    return 0

if __name__ == "__main__":
    sys.exit(main())
