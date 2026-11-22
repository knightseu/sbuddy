# Pilot: MATHCOUNTS 2025 Chapter into crawled_data

Pilot for issue #14 (child of map #8). Run 2026-11-22. Builds on the extraction research in #9 (`docs/research/mathcounts-2025-chapter-pdf-extraction.md` on branch `research/mathcounts-pdf-extraction`) and the format decided in #12.

**Short answer.** The whole Test is now in `crawled_data/mathcounts/2025-chapter/` and imported into a scratch database. That covers 128 Problems (Sprint 30, Target 8, Team 10, Countdown 80), 128 answers, 48 official solutions, 22 Problem figures and 3 solution figures. Re-importing gives identical ids. The pipeline is: text layer for structure, vision for content, a few hand overrides.

- **Machine steps (seconds).** Download, segment, extract units, crop figures and draft the answer key.
- **Reading steps (the real cost).** Problem text, answers and solutions were written by reading the rendered pages: 26 problem pages, 6 answer pages and 8 solution pages. This pilot's reading was done by Claude in-session, about 13 minutes of wall clock for the whole Test.
- **Hand fixes.** Figure overrides (1 excluded, 3 solution figure rectangles), 2 answer alternatives, and the Round format metadata.

No figure needed hand-drawing. Nothing in the Test is missing.

The data stays out of git, because the repo is public. Only the scripts and this report are committed.

## Pipeline

| Step | Tool | Output | Automatic? |
|---|---|---|---|
| Download 6 PDFs | `curl` on `drive.google.com/uc?export=download&id=…` | `_sources/2025-chapter/*.pdf` (archived locally) | yes |
| Segment, units, figure crops, answer draft, solution split | `scripts/mathcounts/extract.py` (PyMuPDF via `uv run --with pymupdf`) | `_work/2025-chapter/draft.json`, `crops/`, `figcrops/`, `pages/` | yes |
| Problem text in LaTeX | vision on rendered pages | `_work/…/content-*.json` | reading |
| Answers | vision on the 6 answer-key pages | `_work/…/answers-*.json` | reading |
| Solutions in LaTeX | vision on the 8 solution pages | `_work/…/sol-*.json` | reading |
| Metadata, alternatives, figure overrides | by hand | `_work/…/review.json` | by hand |
| Assemble | `scripts/mathcounts/build_test.py` (fails if any Problem lacks content or answer) | `2025-chapter/test.json`, `figures/` | yes |
| Import | `scripts/mathcounts/pilotImport.ts` against `sbuddy_pilot` | DB rows, `public/test-images/mathcounts/2025-chapter/` | yes |

## What the measurements say

### Structure: the text layer is fully reliable

- Problem boundaries: 128 of 128.
- Answer units: 55 Problems have one, and every unit matched the answer key once normalised (`cm ^{2}` to `cm²`, `(combi- nations)` to `combinations`). The one bug was `(in) ^{2}`, where the paren closed before the superscript. It was fixed in the normaliser.
- Solution headings: 48 of 48.

### Problem text: vision is needed, and the text layer is a good cross-check

- **Numbers:** in 28 of 128 Problems the sequence of numbers in the text layer differs from the final text. The causes are radicals, stacked fractions, superscripts, vector symbols (♥, ♣, ★), and figure labels mixed into the prose. That's the share that would be wrong without vision.
- **Prose:** word overlap between the text layer and the vision text was at least 90% for 127 of 128. The exception is Sprint 27, whose expression is in a box that the text layer reads out of order. This is a cheap automated guard against invented prose in a bulk run.

### Answer key: vision is needed for fractions and radicals

- **Naive parse:** a positional parse (first token right of `N.`) got **107 of 128** right.
- **The 21 misses:**
  - 11 stacked fractions, where the parse keeps only the denominator.
  - 8 column bleed in Sprint and Target (`264 46`, `13. 14`).
  - 2 radicals (`2√3` and `3∛450` lose the root sign).
- **Vision read:** reading the 6 answer pages got 128 of 128. As a cross-check, all 48 solution final values (the bold answer) agree with the key.

### Figures: automatic, after two heuristic fixes

- **Detection:** drawing clusters at least 30×20 pt, right of x = 160 pt, centred in the Problem band. This found exactly the 22 real figures, plus Sprint 27's box around the expression. The box was excluded by hand, since its content is written as LaTeX.
- **First-pass problems:**
  - Labels above the band were clipped (Countdown 14, 22, 30, 33, 68).
  - Small grids were missed (Countdown 15 is 23 pt tall).
  - Neighbouring prose bled into the padding (Sprint 9 and 12, Countdown 41, 42 and 68).
- **Fixes, now in `extract.py`:**
  - Look for labels across the whole page.
  - Count a span as a label only if its whole line is 10 characters or fewer.
  - Lower the height threshold to 20 pt.
  - Before rendering a figure, redact prose text on a copy of the page, keeping the line art.
- **Result:** all 22 crops are clean, checked on a contact sheet.
- **Data that lives only in a figure was also transcribed** (the Team 2 tally table as numbers, the Sprint 9 table as an `array`), so the Problem can be read without the image.

### Solutions: vision is needed, and the figures need hand rectangles

- **Text layer is unusable:** the Word export's Cambria Math text is corrupted (doubled italics, `𝟏𝟏𝟏𝟏` for 14), so all 48 were transcribed by vision.
- **Correction to #9:** the Solutions PDF's "embedded raster images" are **only label glyphs**, 5–30 px each. The figure lines are vectors, and Word's layout mixes them with fraction bars and underlines, so clustering grabbed most of the page.
- **Workaround:** the 3 solution figures (Sprint 25, Target 2, Target 8) are cropped from page rectangles listed in `review.json`.
- **This Test has no Countdown solutions,** as #9 found.

## Errors by type (what needed a human or vision decision)

| Type | Count | Fix |
|---|---|---|
| Lost or garbled math in problem text | 28 Problems | vision transcription (all) |
| Answer-key parse wrong | 21 / 128 | vision read of key |
| Solution text corrupted | 48 / 48 | vision transcription |
| Figure crop issues (first pass) | 9 | heuristics fixed in code; 1 manual exclude |
| Solution figures not detectable | 3 | hand rectangles |
| Answer alternatives (`12 or 12.00`, `Blue or B`) | 2 | by hand in `review.json` |
| Unit normalisation bug | 1 (2 Problems) | code fix |

## Format and app findings for the implementation slice

1. **The viewer has no Markdown.** `problem.html` puts content in `innerHTML` and runs MathJax; newlines collapse, and `*x*`, `**x**` and `|` tables show up raw. AMC content uses `\textit{…}`/`\textbf{…}` inside `$…$` and never uses newlines. The MATHCOUNTS content follows that convention:
   - tables are `$$\begin{array}…$$`;
   - emphasis is `$\textit{…}$`;
   - currency is `\$`, which works because MathJax has `processEscapes: true`.

   Two solutions still contain `\n` line breaks: the long note in Target 3 and the equation steps in Target 8. Either the viewer gets `white-space: pre-line`, or the format bans newlines.
2. **Solution figures:** the format in #12 has no field for these. The pilot uses the viewer's existing `[DIAGRAM: url]` marker with a relative `figures/…` path, and the importer rewrites it to `/test-images/mathcounts/<test-dir>/…`. Recommend making this part of the format.
3. **The AMC importer breaks under the #11 key.** With `UNIQUE NULLS NOT DISTINCT (test_id, round, problem_number)` in place of `UNIQUE (test_id, problem_number)`, `npm run import:tests:data` failed on all 824 AMC Problems: its `ON CONFLICT (test_id, problem_number)` no longer matches a constraint. It must target the new key in the same change. The pilot migration itself is additive and leaves ids untouched.
4. **Answer unit `$` is a prefix** (Team 3). The viewer should show `$12`, not `12 $`. Either add a prefix flag or special-case `$`.
5. **The `y`-intercept note** in Target 3's solution says `(0, 3)` was ruled *incorrect*. So an answer alternative is not always "any equivalent form". Keep alternatives exactly as printed in the key.
6. **`initializeDatabase()` leaks a pool client.** It checks one out and never releases it, so `db.end()` hangs. Scripts that call it must `process.exit()`. Worth fixing in `database.ts`.

## Implications for the bulk pipeline and coverage

- **Per-Test cost is dominated by reading**, about 40 rendered pages for a Chapter Test with solutions. The machine steps take seconds. The hand steps are small, about five entries in `review.json`.
- **For a bulk run, the reading should be an API vision call per page.** Its output goes into the same `content-*`, `answers-*` and `sol-*` files, guarded automatically by:
  - the text-layer prose-overlap check (≥ 90%);
  - the solution final value equalling the answer key;
  - Problem counts matching `metadata.rounds`;
  - `build_test.py` refusing incomplete Tests.

  No API key for vision is configured in `.env` (`OPENAI_API_KEY` is a placeholder), so this needs one.
- **Roughly 48 Chapter, State and National Tests for 2010–2025** at ~40 pages each comes to ~2,000 page reads. That's feasible in batches. Solution figures (hand rectangles) are the only step that doesn't scale yet, at ~3 per Test.
- **Unknowns:**
  - Older years may be scans with no text layer, which would lose the structural backbone. Check one 2010-era Test before committing to the coverage target.
  - State and National layouts are unverified.
- **Archive the source PDFs:** `_sources/` costs ~3 MB per Test and protects against dead Drive links.

## Reproduce

```sh
# PDFs into crawled_data/mathcounts/_sources/2025-chapter/{sprint,target,team,countdown,answers,solutions}.pdf
uv run --with pymupdf python -I scripts/mathcounts/extract.py \
  crawled_data/mathcounts/_sources/2025-chapter crawled_data/mathcounts/_work/2025-chapter
# ... vision pass writes _work/2025-chapter/{content,answers,sol}-*.json and review.json ...
python3 -I scripts/mathcounts/build_test.py \
  crawled_data/mathcounts/_work/2025-chapter crawled_data/mathcounts/2025-chapter
docker exec sbuddy-postgres psql -U postgres -c "CREATE DATABASE sbuddy_pilot"
DATABASE_URL=postgresql://…/sbuddy_pilot npx ts-node scripts/mathcounts/pilotImport.ts crawled_data/mathcounts
```
