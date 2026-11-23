# MATHCOUNTS data (not in git)

Everything in this folder except this README is gitignored. MATHCOUNTS
material is for personal use only and the repo is public, so it never gets
committed. It lives on the LAN host and is included in backups.

- `_sources/` holds the original PDFs, archived by
  `python3 -I scripts/mathcounts/crawl_sources.py` from
  https://mathteamnyc.weebly.com/mathcounts.html (see #24). Files are named
  `<year>-<level>[-<n>]/<material>.pdf`, for example
  `2025-chapter/countdown.pdf`. `manifest.json` records each file's URL,
  Drive id, size, sha256 and fetch time, plus skipped and failed links.
  Rerunning the script only fetches files that are missing.
- `<year>-<variant>/` holds one extracted Test (`test.json` and `figures/`),
  in the format from #12.
