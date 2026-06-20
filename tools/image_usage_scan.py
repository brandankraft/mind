#!/usr/bin/env python3
"""Report which images in an edition's content/ are referenced by the build,
and which appear unused (candidates for quarantine).

Conservative by design: an image is considered USED if its variant-stripped
base stem appears anywhere in the corpus (all markdown, the engine scripts, and
the index-data JSON). This keeps every variant of any referenced image
(base / -web / -print / -print-bw / -bw / -light / -light-bw), and only flags
images whose whole family is never mentioned.

Usage: image_usage_scan.py <edition_dir> <engine_dir>
Prints KEEP / QUARANTINE lists with counts and sizes. Does NOT move anything.
"""
import sys, os, re

VARIANT_SUFFIXES = ["-print-bw", "-light-bw", "-print", "-light", "-web", "-bw", "300dpi"]
IMG_EXT = (".jpg", ".jpeg", ".png")

def base_stem(filename):
    stem = os.path.splitext(os.path.basename(filename))[0]
    changed = True
    while changed:
        changed = False
        for suf in VARIANT_SUFFIXES:
            if stem.endswith(suf):
                stem = stem[: -len(suf)]
                changed = True
    return stem

def build_corpus(edition_dir, engine_dir):
    parts = []
    content = os.path.join(edition_dir, "content")
    for root, _dirs, files in os.walk(content):
        # don't scan the images themselves, but DO scan md/json/css and front-matter
        for fn in files:
            if fn.lower().endswith((".md", ".json", ".css", ".html")):
                try:
                    parts.append(open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read())
                except Exception:
                    pass
    for root, _dirs, files in os.walk(engine_dir):
        for fn in files:
            if fn.endswith((".py", ".sh")):
                try:
                    parts.append(open(os.path.join(root, fn), encoding="utf-8", errors="ignore").read())
                except Exception:
                    pass
    return "\n".join(parts)

def main():
    edition_dir, engine_dir = sys.argv[1], sys.argv[2]
    content = os.path.join(edition_dir, "content")
    corpus = build_corpus(edition_dir, engine_dir)

    images = []
    for root, _dirs, files in os.walk(content):
        for fn in files:
            if fn.lower().endswith(IMG_EXT):
                images.append(os.path.join(root, fn))

    keep, quarantine = [], []
    for img in images:
        stem = base_stem(img)
        # used if the base stem (or the exact filename) appears in the corpus
        if stem and (stem in corpus or os.path.basename(img) in corpus):
            keep.append(img)
        else:
            quarantine.append(img)

    def total_mb(lst):
        return sum(os.path.getsize(p) for p in lst) / 1048576

    print("images total: %d (%.0f MB)" % (len(images), total_mb(images)))
    print("KEEP:        %d (%.0f MB)" % (len(keep), total_mb(keep)))
    print("QUARANTINE:  %d (%.0f MB)" % (len(quarantine), total_mb(quarantine)))
    print("\n--- QUARANTINE candidates (base stem never referenced) ---")
    for p in sorted(quarantine):
        print("  " + os.path.relpath(p, content))

if __name__ == "__main__":
    main()
