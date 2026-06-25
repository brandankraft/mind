#!/usr/bin/env python3
"""
make_epub_sample.py  --  derive a store-ready SAMPLE epub from the full epub.

Apple Books / KDP "sample" = front matter + the opening chapters only. This
takes the finished full epub and produces a self-contained, epubcheck-clean
sample by KEEPING the spine from the cover through the last chapter before the
cutoff (default: everything up to but not including "Chapter 6", i.e. front
matter + Chapters 1-5), then pruning the manifest/spine/nav/ncx and any
cross-file links that would otherwise dangle.

Usage:
    python3 make_epub_sample.py <full.epub> <sample.epub> [--cut "Chapter 6"]

Pure stdlib (zipfile + re), matching epub_enhance.py's approach. The cutoff is
detected by the first content doc whose <h1> begins with the --cut prefix, so
it survives chapter renumbering; if no such doc is found we abort rather than
ship the whole book mislabeled as a sample.
"""

import sys, os, re, zipfile, shutil, tempfile

CUT_DEFAULT = "Chapter 6"   # first chapter to DROP; keep everything before it


def strip_tags(s):
    return re.sub(r'<[^>]+>', '', s).strip()


def find_opf(tmp):
    container = os.path.join(tmp, 'META-INF', 'container.xml')
    with open(container, encoding='utf-8') as f:
        m = re.search(r'full-path="([^"]+)"', f.read())
    return os.path.join(tmp, m.group(1)), m.group(1)


def parse_manifest(opf_text):
    """id -> dict(href, media, props, tag)."""
    items = {}
    for tag in re.findall(r'<item\b[^>]*/>', opf_text):
        iid = re.search(r'\bid="([^"]*)"', tag)
        href = re.search(r'\bhref="([^"]*)"', tag)
        media = re.search(r'\bmedia-type="([^"]*)"', tag)
        props = re.search(r'\bproperties="([^"]*)"', tag)
        if not (iid and href):
            continue
        items[iid.group(1)] = {
            'href': href.group(1),
            'media': media.group(1) if media else '',
            'props': props.group(1) if props else '',
            'tag': tag,
        }
    return items


def parse_spine(opf_text):
    return re.findall(r'<itemref\b[^>]*\bidref="([^"]*)"[^>]*/?>', opf_text)


def main(full_epub, out_epub, cut_prefix=CUT_DEFAULT):
    tmp = tempfile.mkdtemp(prefix='epubsample-')
    try:
        with zipfile.ZipFile(full_epub) as z:
            z.extractall(tmp)

        opf_path, opf_rel = find_opf(tmp)
        opf_dir = os.path.dirname(opf_path)          # e.g. <tmp>/EPUB
        opf_reldir = os.path.dirname(opf_rel)        # e.g. EPUB
        with open(opf_path, encoding='utf-8') as f:
            opf = f.read()

        manifest = parse_manifest(opf)
        spine = parse_spine(opf)

        def href_of(iid):
            return manifest[iid]['href'] if iid in manifest else None

        def abspath(href):
            # href is relative to the opf dir
            return os.path.normpath(os.path.join(opf_dir, href))

        # ---- find the cutoff: first spine xhtml whose <h1> starts with cut ----
        cut_at = None
        cut_re = re.compile(r'^\s*' + re.escape(cut_prefix) + r'\b', re.I)
        for idref in spine:
            it = manifest.get(idref)
            if not it or 'xhtml' not in it['media']:
                continue
            p = abspath(it['href'])
            if not os.path.exists(p):
                continue
            with open(p, encoding='utf-8') as f:
                doc = f.read()
            h1 = re.search(r'<h1\b[^>]*>(.*?)</h1>', doc, re.S)
            if h1 and cut_re.match(strip_tags(h1.group(1))):
                cut_at = idref
                break
        if cut_at is None:
            print(f'ERROR: cutoff "{cut_prefix}" not found in any chapter <h1> -- '
                  f'refusing to ship a full-book "sample".', file=sys.stderr)
            return 2

        cut_idx = spine.index(cut_at)
        keep_idrefs = spine[:cut_idx]
        drop_idrefs = spine[cut_idx:]

        # ---- kept content-doc hrefs (+ their abs paths) ----------------------
        keep_doc_hrefs = {href_of(i) for i in keep_idrefs if href_of(i)}
        drop_doc_hrefs = {href_of(i) for i in drop_idrefs if href_of(i)}

        # ---- decide which non-spine resources to keep ------------------------
        # Always keep: nav, the ncx, all css, all fonts, the cover image.
        # Images: only those referenced by a kept doc / css.
        spine_toc = re.search(r'<spine\b[^>]*\btoc="([^"]*)"', opf)
        ncx_id = spine_toc.group(1) if spine_toc else None

        keep_ids = set(keep_idrefs)
        for iid, it in manifest.items():
            m, pr = it['media'], it['props']
            if 'nav' in pr or iid == ncx_id or 'dtbncx' in m:
                keep_ids.add(iid)
            elif m == 'text/css':
                keep_ids.add(iid)
            elif m.startswith('font/') or 'font' in m or it['href'].lower().endswith(('.ttf', '.otf', '.woff', '.woff2')):
                keep_ids.add(iid)
            elif 'cover-image' in pr:
                keep_ids.add(iid)

        # scan kept xhtml + css for referenced resources (src=, href=, url())
        referenced = set()
        scan_ids = [i for i in keep_ids
                    if manifest[i]['media'] in ('application/xhtml+xml', 'text/css')]
        for iid in scan_ids:
            p = abspath(manifest[iid]['href'])
            if not os.path.exists(p):
                continue
            base_dir = os.path.dirname(p)
            with open(p, encoding='utf-8', errors='ignore') as f:
                txt = f.read()
            for ref in re.findall(r'(?:src|href)="([^"]+)"', txt) + re.findall(r'url\(([^)]+)\)', txt):
                ref = ref.strip('\'" ').split('#')[0]
                if not ref or ref.startswith(('http:', 'https:', 'data:', 'mailto:')):
                    continue
                referenced.add(os.path.normpath(os.path.join(base_dir, ref)))

        # keep any non-doc resource (image/css/font) whose file is referenced.
        # content docs are decided by the spine ONLY -- never re-add a dropped
        # chapter just because a kept page links to it (those links get unwrapped).
        for iid, it in manifest.items():
            if it['media'] == 'application/xhtml+xml':
                continue
            if abspath(it['href']) in referenced:
                keep_ids.add(iid)

        drop_ids = set(manifest) - keep_ids

        # ---- rewrite the OPF: manifest + spine -------------------------------
        new_opf = opf
        for iid in drop_ids:
            new_opf = new_opf.replace(manifest[iid]['tag'], '')
        for idref in drop_idrefs:
            new_opf = re.sub(r'<itemref\b[^>]*\bidref="' + re.escape(idref) + r'"[^>]*/?>\s*', '', new_opf)
        # mark the title as a sample
        new_opf = re.sub(r'(<dc:title[^>]*>)(.*?)(</dc:title>)',
                         lambda m: m.group(1) + m.group(2) + ' — Free Sample' + m.group(3)
                         if 'Sample' not in m.group(2) else m.group(0),
                         new_opf, count=1, flags=re.S)
        with open(opf_path, 'w', encoding='utf-8') as f:
            f.write(new_opf)

        # the canonical book identifier (ncx must match)
        ident = re.search(r'<dc:identifier[^>]*>([^<]+)</dc:identifier>', opf)
        ident = ident.group(1) if ident else None

        # basenames of dropped docs, for link/nav/ncx pruning
        drop_bases = {os.path.basename(h) for h in drop_doc_hrefs}

        def points_to_dropped(href):
            return os.path.basename(href.split('#')[0]) in drop_bases

        # ---- prune nav.xhtml (toc + landmarks): drop <li> to dropped docs ----
        nav_id = next((i for i, it in manifest.items() if 'nav' in it['props']), None)
        if nav_id:
            navp = abspath(manifest[nav_id]['href'])
            with open(navp, encoding='utf-8') as f:
                nav = f.read()

            def prune_li(text):
                # flat toc (toc-depth=1): each <li> closes its own </li>
                return re.sub(
                    r'<li\b[^>]*>.*?</li>\s*',
                    lambda m: '' if re.search(r'(?:src|href)="([^"]+)"', m.group(0))
                    and points_to_dropped(re.search(r'(?:src|href)="([^"]+)"', m.group(0)).group(1))
                    else m.group(0),
                    text, flags=re.S)

            nav = prune_li(nav)
            with open(navp, 'w', encoding='utf-8') as f:
                f.write(nav)

        # ---- prune toc.ncx: drop navPoints, renumber playOrder, sync uid -----
        if ncx_id and ncx_id in manifest:
            ncxp = abspath(manifest[ncx_id]['href'])
            with open(ncxp, encoding='utf-8') as f:
                ncx = f.read()
            ncx = re.sub(
                r'<navPoint\b[^>]*>.*?</navPoint>\s*',
                lambda m: '' if re.search(r'<content\b[^>]*\bsrc="([^"]+)"', m.group(0))
                and points_to_dropped(re.search(r'<content\b[^>]*\bsrc="([^"]+)"', m.group(0)).group(1))
                else m.group(0),
                ncx, flags=re.S)
            # renumber playOrder sequentially
            counter = [0]
            def _po(m):
                counter[0] += 1
                return f'playOrder="{counter[0]}"'
            ncx = re.sub(r'playOrder="\d+"', _po, ncx)
            # sync dtb:uid to the OPF identifier
            if ident:
                ncx = re.sub(r'(<meta name="dtb:uid" content=")[^"]*(")',
                             lambda m: m.group(1) + ident + m.group(2), ncx)
            with open(ncxp, 'w', encoding='utf-8') as f:
                f.write(ncx)

        # ---- unwrap cross-file links in kept docs that point to dropped ------
        def unwrap_dropped(m):
            href = re.search(r'\bhref="([^"]+)"', m.group(1))
            if href and points_to_dropped(href.group(1)):
                return m.group(2)          # keep the inner text, drop the <a>
            return m.group(0)
        for iid in keep_idrefs:
            it = manifest.get(iid)
            if not it or it['media'] != 'application/xhtml+xml':
                continue
            p = abspath(it['href'])
            if not os.path.exists(p):
                continue
            with open(p, encoding='utf-8') as f:
                doc = f.read()
            doc = re.sub(r'(<a\b[^>]*\bhref="[^"]+"[^>]*>)(.*?)(</a>)',
                         unwrap_dropped, doc, flags=re.S)
            with open(p, 'w', encoding='utf-8') as f:
                f.write(doc)

        # ---- physically delete dropped files ---------------------------------
        for iid in drop_ids:
            p = abspath(manifest[iid]['href'])
            if os.path.exists(p):
                os.remove(p)

        # ---- repack (mimetype first, stored) ---------------------------------
        if os.path.exists(out_epub):
            os.remove(out_epub)
        with zipfile.ZipFile(out_epub, 'w', zipfile.ZIP_DEFLATED) as z:
            mt = os.path.join(tmp, 'mimetype')
            if os.path.exists(mt):
                z.write(mt, 'mimetype', compress_type=zipfile.ZIP_STORED)
            for root, _, files in os.walk(tmp):
                for fn in sorted(files):
                    p = os.path.join(root, fn)
                    rel = os.path.relpath(p, tmp)
                    if rel == 'mimetype':
                        continue
                    z.write(p, rel)

        kept_docs = sum(1 for i in keep_idrefs
                        if manifest.get(i, {}).get('media') == 'application/xhtml+xml')
        size = os.path.getsize(out_epub) / 1048576
        print(f'  sample: kept {kept_docs} content docs (cut at "{cut_prefix}"), '
              f'dropped {len(drop_ids)} manifest items -> {size:.1f} MB')
        return 0
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    cut = CUT_DEFAULT
    if '--cut' in sys.argv:
        cut = sys.argv[sys.argv.index('--cut') + 1]
    if len(args) < 2:
        print('usage: make_epub_sample.py <full.epub> <sample.epub> [--cut "Chapter 6"]', file=sys.stderr)
        sys.exit(1)
    sys.exit(main(args[0], args[1], cut))
