#!/usr/bin/env python3
"""
normalize_pdf.py  <in.pdf>  <out.pdf>

Strips nondeterministic build-time metadata from a WeasyPrint PDF so that two
builds of the same content produce byte-identical normalized outputs.

Fields cleared:
  /CreationDate, /ModDate  -- build timestamps
  /Producer date drift     -- covered by clearing the Info dict
  /ID array in the trailer -- document identifier (randomised by some writers)

WeasyPrint 68.1 does NOT embed /CreationDate or /ModDate and does not write
an /ID array, so in practice the PDFs may already be deterministic.  This
script is a belt-and-suspenders guard for any future writer change.
"""

import sys
import pypdf
import pypdf.generic as g

src, dst = sys.argv[1], sys.argv[2]

r = pypdf.PdfReader(src)
w = pypdf.PdfWriter()
w.append(r)

# Clear Info dict entries that carry timestamps or vary run-to-run.
# add_metadata({}) replaces the entire /Info dict with an empty one.
# We preserve /Producer, /Creator, /Title since those are content-derived.
meta = dict(r.metadata or {})
# Remove the nondeterministic keys; keep the rest
for key in ("/CreationDate", "/ModDate"):
    meta.pop(key, None)
w.add_metadata(meta)

# Freeze the /ID array to a fixed value so any future writer that adds one
# does not cause false FAIL results.
# pypdf 6.x: the writer's trailer is a DictionaryObject; set _ID directly.
try:
    fixed_id = g.ArrayObject([
        g.ByteStringObject(b"\x00" * 16),
        g.ByteStringObject(b"\x00" * 16),
    ])
    w._ID = fixed_id  # written into the trailer by PdfWriter.write()
except Exception:
    pass  # If the internal API changes, skip -- /ID may not exist anyway

with open(dst, "wb") as f:
    w.write(f)
