#!/usr/bin/env python3
"""Audit book PDFs for large white-space areas that aren't legitimate chapter ends.

Renders each page at low DPI, finds the ink bounding box inside the text block,
and measures the empty bands (bottom gap, top gap, biggest internal horizontal
white band, and left/right asymmetry from floats). Flags pages whose worst band
exceeds a threshold, skipping pages that look like real chapter/section ends
(the next page opens with a heading) so we only surface the "cheap-looking" gaps.

Usage: python3 white_space_audit.py <pdf> [<pdf> ...]
"""
import sys, os, subprocess, tempfile, glob
from PIL import Image

DPI = 42
INK = 205                 # pixel < INK counts as ink
MARGIN_FRAC = 0.07        # ignore running header/footer/folio in this outer band
BOTTOM_FLAG = 0.26        # bottom gap > 26% of text block -> flag (unless chapter end)
BAND_FLAG = 0.16          # internal all-white band > 16% -> flag
SIDE_FLAG = 0.30          # one side empty for >30% of text-block height -> float gap

def ink_rows_cols(im):
    g = im.convert("L")
    w, h = g.size
    px = g.load()
    mx = int(w * MARGIN_FRAC); my = int(h * MARGIN_FRAC)
    x0, x1, y0, y1 = mx, w - mx, my, h - my
    row_ink = []   # (has_ink, left_ink_x, right_ink_x) per row in text block
    for y in range(y0, y1):
        l = None; r = None
        for x in range(x0, x1):
            if px[x, y] < INK:
                if l is None: l = x
                r = x
        row_ink.append((l is not None, l, r))
    return row_ink, (x0, x1, y0, y1)

def analyze(path_png):
    im = Image.open(path_png)
    rows, (x0, x1, y0, y1) = ink_rows_cols(im)
    H = len(rows)
    if H == 0: return None
    tb_w = x1 - x0
    inked = [i for i, r in enumerate(rows) if r[0]]
    if not inked:
        return {"blank": True, "bottom": 1.0, "top": 1.0, "band": 1.0, "side": 0.0}
    top_gap = inked[0] / H
    bottom_gap = (H - 1 - inked[-1]) / H
    # largest internal all-white band between first and last ink row
    band = 0; run = 0
    for i in range(inked[0], inked[-1] + 1):
        if not rows[i][0]:
            run += 1; band = max(band, run)
        else:
            run = 0
    band /= H
    # float side-gap: among inked rows, fraction where ink occupies only left
    # half or only right half (text crammed beside a wide float)
    half = x0 + tb_w * 0.5
    left_only = right_only = 0
    for has, l, r in rows:
        if not has: continue
        if r is not None and r < x0 + tb_w * 0.55: left_only += 1
        elif l is not None and l > x0 + tb_w * 0.45: right_only += 1
    side = max(left_only, right_only) / H
    return {"blank": False, "top": top_gap, "bottom": bottom_gap, "band": band, "side": side}

def audit_pdf(pdf):
    name = os.path.basename(pdf)
    tmp = tempfile.mkdtemp(prefix="wsaudit-")
    subprocess.run(["pdftoppm", "-r", str(DPI), "-png", pdf, os.path.join(tmp, "p")],
                   check=True, capture_output=True)
    pages = sorted(glob.glob(os.path.join(tmp, "p-*.png")))
    stats = []
    for pg in pages:
        n = int(os.path.basename(pg).split("-")[1].split(".")[0])
        a = analyze(pg)
        if a: a["page"] = n; stats.append(a)
    # a page is a likely chapter/section END if the NEXT page is a chapter OPEN
    # (big top gap on next page). Mark those so we don't flag their bottom gap.
    opens = {s["page"] for s in stats if not s["blank"] and s["top"] > 0.33}
    flagged = []
    for s in stats:
        if s["blank"]:
            continue
        reasons = []
        chapter_end = (s["page"] + 1) in opens
        if s["bottom"] > BOTTOM_FLAG and not chapter_end:
            reasons.append(f"bottom {int(s['bottom']*100)}%")
        if s["band"] > BAND_FLAG:
            reasons.append(f"midband {int(s['band']*100)}%")
        if s["side"] > SIDE_FLAG:
            reasons.append(f"float-side {int(s['side']*100)}%")
        if reasons:
            flagged.append((s["page"], s["bottom"], s["band"], s["side"], ", ".join(reasons)))
    subprocess.run(["rm", "-rf", tmp])
    flagged.sort(key=lambda t: -(t[1] + t[2] + t[3]))
    print(f"\n===== {name}  ({len(pages)} pp, {len(flagged)} flagged) =====")
    for pg, b, band, side, why in flagged[:60]:
        print(f"  p{pg:<5} {why}")
    return name, len(pages), flagged

if __name__ == "__main__":
    for pdf in sys.argv[1:]:
        audit_pdf(pdf)
