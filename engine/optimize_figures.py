#!/usr/bin/env python3
"""Measure which centered figures bumped to a fresh page (leaving the previous
page short) and write per-trim max-height overrides that pull each one back up
to fill the gap. Only reduces max-height -- aspect ratio is preserved, so images
never distort.

Usage: optimize_figures.py <pdf> <trim-key> <book_source_dir>
Writes <book_source_dir>/index-data/figure-overrides-<trim-key>.json  ({stem: max_in})

build-book-pdf.py reads that file and emits  img[src*="stem"]{max-height:Nin}.
Run: build (no/old overrides) -> this -> build again.
"""
import sys, os, re, json, glob, subprocess, tempfile, statistics
from PIL import Image
from pypdf import PdfReader

DPI = 110
INK = 205
MF = 0.055           # ignore header/footer/folio band
TOP_OF_PAGE = 0.42   # caption in top 42% => figure sits at page top (it bumped here)
GAP_MIN = 0.15       # prior-page bottom gap must exceed this frac of text block
SAFETY = 0.92        # target slightly under the measured gap
FLOOR_IN = 1.5       # never shrink an image below this

PDF, TRIM, SRC = sys.argv[1], sys.argv[2], sys.argv[3]

# --- 1. standalone centered figures from source: (stem, caption first words) ---
FIG_RE = re.compile(
    r'<figure class="book-figure-(?:center|portrait)"[^>]*>\s*'
    r'<img src="([^".]+)\.(?:jpg|jpeg|png)"[^>]*/?>\s*'
    r'(?:<figcaption>(.*?)</figcaption>)?', re.S)
figs = []
for md in glob.glob(os.path.join(SRC, "*.md")):
    t = open(md).read()
    for m in FIG_RE.finditer(t):
        stem = os.path.basename(m.group(1))
        cap = re.sub(r'<[^>]+>', '', m.group(2) or '')
        cap = cap.replace('*', '').strip()
        if cap:
            figs.append((stem, cap))

# --- 2. render all pages once + grab per-page text ---
tmp = tempfile.mkdtemp(prefix="figfit-")
subprocess.run(["pdftoppm", "-r", str(DPI), "-png", PDF, os.path.join(tmp, "p")],
               check=True, capture_output=True)
paths = sorted(glob.glob(os.path.join(tmp, "p-*.png")))
pad = len(os.path.basename(paths[0]).split("-")[1].split(".")[0])
def ppath(n): return os.path.join(tmp, f"p-{str(n).zfill(pad)}.png")

reader = PdfReader(PDF)
page_text = [(p.extract_text() or "") for p in reader.pages]

# --- 3. per-page ink geometry (first/last ink row inside the text block) ---
def ink_extent(n):
    im = Image.open(ppath(n)).convert("L")
    w, h = im.size
    mx, my = int(w * MF), int(h * MF)
    crop = im.crop((mx, my, w - mx, h - my))
    mask = crop.point(lambda p: 255 if p < INK else 0)   # ink -> nonzero
    bbox = mask.getbbox()                                 # C-level, fast
    if bbox is None:
        return None, None, h
    return bbox[1] + my, bbox[3] + my, h

geom = {}
for n in range(1, len(paths) + 1):
    geom[n] = ink_extent(n)

# calibrate text-block top/bottom (median over full pages) -> inches
tops = [g[0] for g in geom.values() if g[0] is not None]
bots = [g[1] for g in geom.values() if g[1] is not None]
tb_top = statistics.median(tops)
tb_bot = statistics.median(bots)
T_in = (tb_bot - tb_top) / DPI    # text block height in inches

def caption_lines(cap, trim):
    cpl = {"6x9": 52, "7x10": 60, "8.5x11": 70, "webpdf": 60}.get(trim, 60)
    return max(1, -(-len(cap) // cpl))   # ceil

# --- 4. for each figure: find its page, detect bump, compute target ---
overrides = {}
placement = {}
report = []
for stem, cap in figs:
    needle = " ".join(cap.split()[:8])
    pg = None
    for i, txt in enumerate(page_text):
        if needle and needle in " ".join(txt.split()):
            pg = i + 1; break
    if not pg or pg < 2:
        continue
    first, last, h = geom[pg]
    if first is None:
        continue
    # figure must sit at the top of its page (it bumped here)
    if (first - tb_top) / (tb_bot - tb_top) > TOP_OF_PAGE:
        continue
    # measure the previous page's bottom gap
    pf, pl, ph = geom[pg - 1]
    if pl is None:
        continue
    gap_frac = (tb_bot - pl) / (tb_bot - tb_top)
    fill_frac = (pl - tb_top) / (tb_bot - tb_top)
    if gap_frac < GAP_MIN or fill_frac < 0.40:
        continue   # not a real bump (chapter end / mostly empty prior page)
    gap_in = gap_frac * T_in
    cap_allow = caption_lines(cap, TRIM) * 0.155 + 0.45   # caption + figure margins
    target = round(gap_in * SAFETY - cap_allow, 2)
    if target < FLOOR_IN:
        # gap too small to fit a usably-sized image+caption -> REPOSITION instead:
        # move the figure down a paragraph so text fills the gap (per-trim placement).
        placement[stem] = True
        report.append(f"  {stem:26} pg{pg}  prev-gap {int(gap_frac*100)}%  -> reposition (down +1 para)")
        continue
    overrides[stem] = target
    report.append(f"  {stem:26} pg{pg}  prev-gap {int(gap_frac*100)}%  -> max-height {target}in")

subprocess.run(["rm", "-rf", tmp])

os.makedirs(os.path.join(SRC, "index-data"), exist_ok=True)
out = os.path.join(SRC, "index-data", f"figure-overrides-{TRIM}.json")
# Merge with any existing overrides from prior passes: only ever shrink FURTHER
# (take the smaller max-height), so re-running converges instead of oscillating.
existing = {}
if os.path.exists(out):
    try: existing = json.load(open(out))
    except Exception: existing = {}
merged = dict(existing)
for k, v in overrides.items():
    merged[k] = min(v, existing[k]) if k in existing else v
new_count = sum(1 for k in overrides if k not in existing or overrides[k] < existing.get(k, 9e9))
# a figure that needs repositioning shouldn't ALSO be resized
for k in placement:
    merged.pop(k, None)
json.dump(merged, open(out, "w"), indent=1)

# --- placement file: {stem: shift_paragraphs}. Each pass a figure still bumps,
# bump its shift by 1 (the build already applied the prior shift, so it needs more).
pout = os.path.join(SRC, "index-data", f"figure-placement-{TRIM}.json")
pexist = {}
if os.path.exists(pout):
    try: pexist = json.load(open(pout))
    except Exception: pexist = {}
pmerged = dict(pexist)
for k in placement:
    pmerged[k] = int(pexist.get(k, 0)) + 1
json.dump(pmerged, open(pout, "w"), indent=1)

print(f"trim={TRIM}  text-block={T_in:.2f}in  figures={len(figs)}  resize={len(merged)}  reposition={len(pmerged)}")
print("\n".join(report))
print(f"wrote {out}\nwrote {pout}")
