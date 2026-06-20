#!/usr/bin/env python3
"""Compare two PDFs for CONTENT equality, ignoring WeasyPrint's path-derived
image XObject names (/i<md5-of-source-path>).

WeasyPrint 68.1 names each embedded image XObject by a hash of its source file
path. Building the book from a different absolute directory therefore changes
every image id -- and those ids appear both in plaintext object dicts and inside
FlateDecode content streams -- so the raw bytes differ even when the rendered
book (text, fonts, image pixels, layout) is byte-for-byte identical.

This tool normalizes that cosmetic difference away:
  1. decompress every FlateDecode stream (so embedded /i<hash> ids become plaintext),
  2. canonicalize /i<32-hex> ids to sequential tokens in first-appearance order,
  3. byte-compare the normalized results.

Exit 0 => content-identical.  Exit 1 => a real difference remains (and it prints
the first differing region for inspection).

Usage: pdf_content_equal.py A.pdf B.pdf
"""
import sys, re, zlib

NAME = re.compile(rb'/i[0-9a-f]{32}')

# Match a FlateDecode stream object body and decompress it in place so any
# image-id references inside become plaintext (and re-canonicalizable).
STREAM = re.compile(rb'(/Filter\s*/FlateDecode[^>]*>>\s*stream\r?\n)(.*?)(\r?\nendstream)', re.DOTALL)

def inflate_streams(data: bytes) -> bytes:
    out = []
    pos = 0
    for m in STREAM.finditer(data):
        out.append(data[pos:m.start()])
        body = m.group(2)
        try:
            dec = zlib.decompress(body)
            # mark as decoded: drop the /Filter so the dict still parses loosely,
            # but for pure byte-comparison we just substitute decoded bytes.
            out.append(b'/DecodedStream>>\nstream\n' + dec + b'\nendstream')
        except Exception:
            out.append(m.group(0))  # not really flate / nested -> leave as-is
        pos = m.end()
    out.append(data[pos:])
    return b''.join(out)

XREF_ENTRY = re.compile(rb'\d{10} \d{5} [nf]')
STARTXREF = re.compile(rb'startxref\s+\d+')

def canon_names(data: bytes) -> bytes:
    seen = {}
    def rep(m):
        k = m.group(0)
        if k not in seen:
            seen[k] = ("/iC%08d" % len(seen)).encode()
        return seen[k]
    data = NAME.sub(rep, data)
    # Neutralize byte-offset bookkeeping (xref entries + startxref): these shift
    # purely because the canonical id length differs from the original hash, not
    # because any content changed.
    data = XREF_ENTRY.sub(b'0000000000 00000 n', data)
    data = STARTXREF.sub(b'startxref 0', data)
    return data

def normalize(path: str) -> bytes:
    data = open(path, 'rb').read()
    return canon_names(inflate_streams(data))

def main():
    a, b = sys.argv[1], sys.argv[2]
    na, nb = normalize(a), normalize(b)
    if na == nb:
        print("CONTENT-IDENTICAL")
        return 0
    # report first diff
    n = min(len(na), len(nb))
    for i in range(n):
        if na[i] != nb[i]:
            lo = max(0, i - 60)
            print("DIFFERS at normalized offset", i)
            print("A:", na[lo:i+60])
            print("B:", nb[lo:i+60])
            break
    else:
        print("DIFFERS in length only:", len(na), "vs", len(nb))
    return 1

if __name__ == "__main__":
    sys.exit(main())
