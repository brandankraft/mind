#!/usr/bin/env python3
"""
normalize_pdf.py  <in.pdf>  <out.pdf>

Strips nondeterministic build-time metadata from a WeasyPrint PDF so that two
builds of the same content produce byte-identical normalized outputs.

Fields cleared:
  /CreationDate, /ModDate  -- build timestamps
  /Producer date drift     -- covered by clearing the Info dict
  /ID array in the trailer -- document identifier (randomised by some writers)

WeasyPrint internal XObject names are path-dependent (MD5 of the image URL,
which includes the absolute source directory).  Two builds from different
source trees produce different names but identical content.  We canonicalize
them to sequential same-length names (n<zero-padded-index>) in document order
so that content-identical PDFs compare equal regardless of where they were
built.

The replacement is same-length (33 chars: n + 32-digit decimal) to avoid
corrupting the PDF's byte-offset-based cross-reference table.
"""

import sys
import re
import pypdf
import pypdf.generic as g
import tempfile
import os

src, dst = sys.argv[1], sys.argv[2]

# ------------------------------------------------------------------
# Pass 1: read the raw bytes and rename path-dependent XObject IDs
# ------------------------------------------------------------------
# WeasyPrint names image XObjects as  i<md5(url)><0|1>  where md5(url) is 32
# lowercase hex chars and the trailing digit is the interpolate flag (0 or 1).
# Total name length = 33 chars (without the leading /). The leading / is NOT
# part of the capture group so the replacement must also be 33 chars.
#
# We replace every such name with a canonical n<32-digit-decimal> (same 33
# chars) so two builds from different source directories compare equal.
XOBJ_PAT = re.compile(rb'/i([0-9a-f]{32}[01])(?=[\s/<>\[\]()\000])')

with open(src, "rb") as f:
    raw = f.read()

# Collect all unique IDs in the order they first appear.
seen = {}
for m in XOBJ_PAT.finditer(raw):
    name = m.group(1)
    if name not in seen:
        seen[name] = len(seen)

def _replace(m):
    idx = seen[m.group(1)]
    # Canonical name: n + 32-digit zero-padded decimal = 33 chars, same as original.
    canonical = f"n{idx:032d}".encode()
    return b"/" + canonical

raw2 = XOBJ_PAT.sub(_replace, raw)

# Write to a temp file for pypdf to read.
tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
tmp.write(raw2)
tmp.close()

# ------------------------------------------------------------------
# Pass 2: pypdf metadata normalization (timestamps, /ID)
# ------------------------------------------------------------------
r = pypdf.PdfReader(tmp.name)
w = pypdf.PdfWriter()
w.append(r)

# Clear Info dict entries that carry timestamps or vary run-to-run.
# We preserve /Producer, /Creator, /Title since those are content-derived.
meta = dict(r.metadata or {})
for key in ("/CreationDate", "/ModDate"):
    meta.pop(key, None)
w.add_metadata(meta)

# Freeze the /ID array to a fixed value.
try:
    fixed_id = g.ArrayObject([
        g.ByteStringObject(b"\x00" * 16),
        g.ByteStringObject(b"\x00" * 16),
    ])
    w._ID = fixed_id
except Exception:
    pass

with open(dst, "wb") as f:
    w.write(f)

os.unlink(tmp.name)
