# Deploy

This repo stops at `output/`. It builds files; it does not ship them.

## The seam

```
Mind repo                         PristineGrace repo
---------                         ------------------
engine/build.sh 1st-edition       (separate step, owned by PristineGrace)
  -> editions/1st-edition/
       output/
         web-html/      --------> public_html/book-content/chapters/ + chapters.json
         web-pdf/       --------> public_html/book-content/downloads/
         epub/          --------> public_html/book-content/downloads/
         7x10-color/    (local only -- uploaded to IngramSpark directly)
         7x10-bw/       (local only)
         8.5x11/        (local only)
         6x9/           (local only)
```

## What PristineGrace does

The PristineGrace project (at `~/PristineGrace/`) picks up the built output files and deploys them to the live site (pristinegrace.org). The mechanism is:

- Web HTML: chapter `.html` files and `chapters.json` from `output/web-html/` are copied into `public_html/book-content/chapters/` on the server (Joshua).
- Downloads (web PDF and EPUB): the version-stamped PDFs and EPUBs from `output/web-pdf/` and `output/epub/` are copied into `public_html/book-content/downloads/`.

PristineGrace manages this copy step via its own `deploy.sh` and `upload.sh` scripts. Those scripts live in `~/PristineGrace/scripts/` and are not part of this repo.

## What this repo does NOT do

- No SSH to Joshua.
- No `rsync` to production.
- No `git push` to any remote.
- The engine has no `REMOTE_HOST`, `REMOTE_PATH`, or deploy step. The original `build-book.sh` in PristineGrace had these; they were removed from the engine copy in this repo.

## Print interiors

`7x10-color`, `7x10-bw`, `8.5x11`, and `6x9` are local-only. The PDF is uploaded to IngramSpark manually via their dashboard. This repo does not automate that upload.

## GitHub Releases

Built artifacts are version-stamped (`a-thought-in-the-mind-of-god-1.0-web-pdf.pdf`) and intended to be published as GitHub Releases on this repo -- outside the git tree, since `output/` is gitignored. This keeps the repo lean (no multi-hundred-MB PDFs in history) while preserving a versioned public record of each release.

## Updating the PristineGrace deploy path

After the Mind2 -> Mind cutover, PristineGrace's deploy step needs to be repointed from the old Mind working tree to `editions/1st-edition/output/`. That is a one-line change in PristineGrace's deploy tooling. It is tracked there, not here.
