#!/usr/bin/env python3
"""Pre-bake right-sized print image variants into book_dir/print-sized/.

Every IngramSpark print build runs weasyprint over the whole 962-page book 2-3
times, each pass embedding the source rasters at FULL resolution even though most
print at 1-5 inches (far above 300 ppi). downsample_print_images() fixes the
final PDF but can't speed those renders. This tool moves the resize UPSTREAM,
NON-DESTRUCTIVELY:

  * It measures each image's printed size from a built print PDF.
  * For every file the print build actually embeds (the resolved -print/-light/
    original color file), it writes a right-sized copy into book_dir/print-sized/
    -- NEVER overwriting the original or the authored -light diagram plates.
  * It emits index-data/print-image-inches.json {resolved_basename: [w_in,h_in]}.

The build's _swap_to_print_variants() routes every resolved src through
_print_sized(), which (when a json entry exists and the source is bigger than
target) returns the cached print-sized/<name> copy. _grayscale_images() then
derives its -bw from that already-small file. Result: 2-3x less image data per
render. downsample_print_images() stays as the per-trim precision safety net, so
a stale json only ever costs mild softness, never an over-600-ppi flag.

Sizes are measured at the 7x10 trim; that is the binding (smallest-text-block)
print trim for fixed-inch figures, and full-width images in the wider 8.5x11
stay >=250 ppi (still print-grade; the safety net never upsizes).

Usage:
  python3 scripts/prebake_print_images.py <book_dir> <print_pdf> <build_html> [--apply] [--ppi N]
"""
import os, sys, json, math, re
from pypdf import PdfReader
from pypdf.generic import ContentStream
from PIL import Image

book_dir = os.path.abspath(sys.argv[1])
pdf_path = sys.argv[2]
html_path = sys.argv[3]
APPLY = "--apply" in sys.argv
PPI = 320.0
if "--ppi" in sys.argv: PPI = float(sys.argv[sys.argv.index("--ppi")+1])
TOL = 1.05
CACHE = os.path.join(book_dir, "print-sized")
JSON_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index-data", "print-image-inches.json")

def strip_bwweb(stem):
    while True:
        m = re.match(r"^(.*)-(bw|web)$", stem)
        if not m: return stem
        stem = m.group(1)

# 1. resolved color files the print build embeds = strip -bw/-web from build-html srcs
with open(html_path) as fh:
    html = fh.read()
embedded = set()
for s in re.findall(r'src="([^"]+\.(?:png|jpg|jpeg))"', html):
    stem, ext = os.path.splitext(os.path.basename(s))
    resolved = strip_bwweb(stem) + ext
    embedded.add(resolved)

def ahash(im):
    g = im.convert("L").resize((8, 8))
    px = list(g.getdata()); avg = sum(px)/len(px); b = 0
    for i, p in enumerate(px):
        if p >= avg: b |= (1 << i)
    return b
def ham(a, b): return bin(a ^ b).count("1")
def mul(a, b):
    return [a[0]*b[0]+a[1]*b[2], a[0]*b[1]+a[1]*b[3], a[2]*b[0]+a[3]*b[2],
            a[2]*b[1]+a[3]*b[3], a[4]*b[0]+a[5]*b[2]+b[4], a[4]*b[1]+a[5]*b[3]+b[5]]

# 2. printed size per XObject + decode hash
reader = PdfReader(pdf_path)
disp = {}
for page in reader.pages:
    res = page.get("/Resources")
    if not res: continue
    xo = res.get_object().get("/XObject")
    if not xo: continue
    xo = xo.get_object()
    n2i = {nm: ref.idnum for nm, ref in xo.items() if ref.get_object().get("/Subtype") == "/Image"}
    cs = ContentStream(page.get_contents(), reader); ctm = [1,0,0,1,0,0]; stk = []
    for ops, op in cs.operations:
        if op == b"q": stk.append(ctm[:])
        elif op == b"Q": ctm = stk.pop() if stk else [1,0,0,1,0,0]
        elif op == b"cm": ctm = mul([float(x) for x in ops], ctm)
        elif op == b"Do" and ops[0] in n2i:
            w = math.hypot(ctm[0],ctm[1])/72.0; h = math.hypot(ctm[2],ctm[3])/72.0
            idn = n2i[ops[0]]; pw, ph = disp.get(idn,(0,0)); disp[idn] = (max(pw,w),max(ph,h))
xh = {}
for imf in reader.pages[0].images:
    idn = imf.indirect_reference.idnum
    if idn in disp and idn not in xh:
        im = imf.image
        xh[idn] = (ahash(im), im.width/im.height if im.height else 0)

# 3. match each resolved file -> nearest XObject -> printed inches
sizes = {}
plan = []
for fn in sorted(embedded):
    p = os.path.join(book_dir, fn)
    if not os.path.exists(p):
        plan.append((fn, "MISSING", None, None, None)); continue
    im = Image.open(p); fa = ahash(im); asp = im.width/im.height if im.height else 0
    best, bd = None, 999
    for idn,(a, xasp) in xh.items():
        if asp and xasp and abs(asp-xasp)/asp > 0.05: continue
        d = ham(fa, a)
        if d < bd: bd, best = d, idn
    if best is None:
        plan.append((fn, "NO-XOBJ", (im.width,im.height), None, None)); continue
    win, hin = disp[best]
    sizes[fn] = [round(win,3), round(hin,3)]
    tw, th = round(win*PPI), round(hin*PPI)
    need = im.width > tw*TOL or im.height > th*TOL
    plan.append((fn, f"d{bd}", (im.width,im.height), (tw,th), need))

# 4. report + (optionally) write cache + json
print(f"{'resolved file':>34} {'match':>6} {'src px':>12} {'->print px':>12} need")
nwrite = 0
for fn, tag, spx, tpx, need in sorted(plan, key=lambda x: (x[4] is not True, x[0])):
    print(f"{fn:>34} {tag:>6} {str(spx):>12} {str(tpx):>12} {'YES' if need else '-'}")
    if APPLY and need:
        im = Image.open(os.path.join(book_dir, fn))
        win, hin = sizes[fn]; tw, th = max(1,round(win*PPI)), max(1,round(hin*PPI))
        scale = min(tw/im.width, th/im.height)
        small = im.resize((max(1,round(im.width*scale)), max(1,round(im.height*scale))), Image.LANCZOS)
        os.makedirs(CACHE, exist_ok=True)
        out = os.path.join(CACHE, fn)
        ext = os.path.splitext(fn)[1].lower()
        if ext in (".jpg", ".jpeg"):
            small.convert("RGB").save(out, "JPEG", quality=92, optimize=True)
        else:
            small.save(out, "PNG", optimize=True)
        nwrite += 1
if APPLY:
    os.makedirs(os.path.dirname(JSON_OUT), exist_ok=True)
    with open(JSON_OUT, "w") as fh:
        json.dump(sizes, fh, indent=1, sort_keys=True)
    print(f"\nWrote {nwrite} cached variants to {CACHE}")
    print(f"Wrote size map: {os.path.relpath(JSON_OUT, book_dir) if False else JSON_OUT} ({len(sizes)} entries)")
else:
    print(f"\n(report only) resolved files: {len(embedded)}  matched: {len(sizes)}  would resize: {sum(1 for p in plan if p[4] is True)}")
