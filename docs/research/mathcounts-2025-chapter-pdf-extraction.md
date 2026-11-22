# MATHCOUNTS 2025 Chapter PDFs: contents and extractability

Research for issue #9 (child of map #8). Researched 2026-11-22.

**Short answer.** All six files are born-digital PDFs (InDesign or Word), not scans. They have a full text layer. Anyone can download them from Google Drive without signing in. The text layer splits the Rounds into Problems perfectly: 30 / 8 / 10 / 80 problems, contiguous, found with a trivial rule. Prose comes through clean. Math does not: radicals, stacked fractions and some inline symbols are vector drawings, so they drop out of the text. Superscripts flatten, though span metadata can recover them. Figures are vector drawings, so they can be cropped per Problem at any resolution. Reading the rendered pages with LLM vision reproduced every sampled Problem exactly, math and figure data included. The repo's Surya OCR service is not reachable. Recommendation for the follow-up ticket: a **hybrid**. Use the text layer for boundaries, numbering, units and the answer key. Use LLM vision on per-Problem crops for the final problem text, with math in LaTeX. Store a rendered crop of each figure.

## Sources

| File | Drive id | Pages | Producer | Doc code |
|---|---|---|---|---|
| Sprint | `1VtOHtuYRYRkWRXdSXaRHkjesaY0a9cJV` | 8 | Adobe InDesign 19.2 | 02-C25SPR |
| Target | `1B7Rqpjb0W06mHCqeV1bd7oSmTCeBxs6t` | 6 | Adobe InDesign 19.2 | none printed |
| Team | `1jZAKklYXp9Miuj21QN_aThCR4uyHczET` | 4 | Adobe InDesign 19.2 | 02-C25TEA |
| CDR (Countdown) | `1f6HHBHRyzdeMS-P4IE85-0IDF-C1ENar` | 8 | Adobe InDesign 19.2 | 02-C25CDR |
| Answers | `1mA5OIEUrgUHlXhw4G6AwcazcW6cDD_1Y` | 8 | Adobe InDesign 19.2 | 02-C25ANS |
| Solutions | `1h2qCRb6d25K3uYLrHozQlpD4pIJMdpH5` | 9 | Acrobat PDFMaker 24 for Word | none |

The links come from the "2025 / CHAPTER" row of https://mathteamnyc.weebly.com/mathcounts.html. That row also links a Handbook, which is out of scope. The PDF title metadata names the Round, e.g. "2025 Chapter Competition Sprint Round". The PDFs were downloaded to `/tmp` and inspected with PyMuPDF 1.26 (`pymupdf`) in a throwaway venv. poppler (`pdftotext`/`pdfinfo`) is not installed on this machine. PyMuPDF reads the same text layer, so `pdftotext` would hit the same issues described below. The PDFs are **not** committed; quotes below are short excerpts for illustration.

## 1. Download and authentication

- `GET https://drive.google.com/uc?export=download&id=<ID>` returns `303` to `https://drive.usercontent.google.com/download?id=<ID>&export=download`. That URL returns `200 application/octet-stream`, and the body starts with `%PDF-1.6`. **No cookies or auth are needed.** All six files are 250–760 KB.
- Drive only shows its "can't scan for viruses" interstitial for large files (widely reported as roughly 100 MB or more; not verified here). These files are far below that. A bulk importer should still check that the body starts with `%PDF` before trusting it.
- The ids come from the `.../file/d/<ID>/view?usp=sharing` hrefs on the Weebly page. A crawler can regex them out of the page HTML. The page is a two-column table per year, with lines labelled `CHAPTER:`, `STATE:` and `NATIONAL:`. Each line is a list of `<a>` elements whose text is the material name (Sprint, Target, Team, CDR, Answers, Solutions, Handbook, Results).

## 2. Text layer: yes, full, born-digital

Every page except the cover and the trailing blank page has a real text layer. The fonts are embedded Times New Roman, Akzidenz Grotesk, Symbol and Cambria Math. The problem PDFs embed exactly one raster image, the sponsor logos on the cover. All problem figures are **vector drawings**, not images.

### Problem boundaries: perfect

Each Problem starts with a word matching `^\d+\.$` at x < 60 pt, followed by the answer blank `_____`. Splitting each page into bands between consecutive anchors, ending at the `Copyright` footer, gives:

| Round | Problems found | Contiguous 1..N | Problems per page |
|---|---|---|---|
| Sprint | 30 | yes | 5 |
| Target | 8 | yes | 2 (one pair per page side) |
| Team | 10 | yes | 5 |
| Countdown | 80 | yes | ~15 |

No Problem crosses a page boundary.

### Units: in the answer blank

The unit is printed in small type inside the answer blank, between the blank and the problem text (x ≈ 120–200 pt). Examples: `years`, `cm2`, `in3`, `ordered pairs`, `ways`, `units2`, `years old` (on two lines), `$` before the blank (Team 3), `inches`. In Countdown the unit is in parentheses: `(dollars)`, `(cm2)`, `(combi- nations)` (hyphenated across two lines). Superscripts in units are flattened (`cm2`) unless span flags are used.

### Prose: clean

For example, Target 1 ("While practicing for MATHCOUNTS, Eli attempted to add the first ten positive integers, accidentally left one out…") extracts exactly, and so do most word problems.

### Math notation: lossy, in four distinct ways

1. **Superscripts are flattened but recoverable.** `2^10` extracts as `210` (Countdown 2: "a divisor of 210 … a divisor of 123"), `a^b × c^d` as `a b × c d`, and `4^m` as `4m`. This changes the meaning. However, the exponent is a separate 7 pt span with PyMuPDF's superscript flag (`flags & 1`) set, so a span-aware extractor can rebuild `2^{10}`. Inside equation objects the flag is *not* set (Sprint 28: the `2` in `75²` is a 6.5 pt span with no flag), so a size/baseline heuristic is also needed.
2. **Radicals are lost.** The radical sign and vinculum are drawn as vectors. `√(6+2√5)` extracts as `6 + 2 5` (Sprint 23), `√(20√25)` as `20 25` (Countdown 5), and `√(75²+1)` as `75 2 + 1` (Sprint 28). This cannot be recovered from text.
3. **Stacked fractions are split across lines.** `(12−♥)/3 = 1` (Sprint 6) extracts as `12` on one line and `If 1, what is …` on the next, with the `3` far to the right. `22!/20!` (Countdown 26) and the `1/2` and `1/3` in Team 4 behave the same way. Geometry can sometimes rebuild them, but not reliably.
4. **Some inline symbols are vectors or mis-mapped glyphs.** The ♥ inside Sprint 6's fraction and the ★ in Countdown 80 ("what color is the vertex with the ?") are drawings, so they are missing from the text. Sprint 10's `V_sphere = (4/3)πr³` extracts as `Vsphere O °r`: the Symbol-font glyphs for `=` and `π` map to the wrong Unicode.

### Figure labels: noisy

Text inside figures is extracted. In layout-sorted mode it interleaves with the problem prose. Some labels appear **twice**: Sprint 4's spinner gives `4848 2121 3737 1515 1212`, because each number is drawn as two identical spans at the same position, probably fill plus outline. Dedupe spans by (text, bbox).

### Data drawn as vectors: lost

In Team 2 the contingency table's header text extracts, but the **tally marks** that carry the data are vectors. The Problem cannot be solved from the text layer.

## 3. Figures and per-Problem cropping

- Figures sit to the right of the problem text, inside the Problem's band. Sometimes they rise above the Problem number line by 5–25 pt (Sprint 9 graph, Countdown 30 and 33). Because they are vectors, `page.get_pixmap(clip=rect, dpi=…)` renders them crisply at any DPI.
- **Band crop** (full width, from this anchor to the next): this works for Sprint, Target and Team, but clips the top of figures that rise above the anchor. Fix: cluster the page's drawings, ignoring the full-page frame rectangle, and grow each band by every cluster whose vertical centre lies in it. That captured every figure in the sample. In the dense Countdown booklet, the grown band can include one line of the neighbouring Problem's text (seen for Countdown 30 and 33).
- **Figure-only crop** (drawing cluster plus nearby short label words, plus padding): this gives clean figure images, e.g. Countdown 33's triangle with labels `X Y Z 2x + 5 6x − 7`. The label heuristic sometimes pulls in a neighbouring word of prose (seen on Team 2's table). It needs tuning, or a final vision check.
- Note: PyMuPDF's built-in `cluster_drawings()` returns one cluster for the whole page because of the page frame, so a custom clustering pass is needed.
- Solutions are different. They come from Word, and their figures are **embedded raster images** (8, 9 and 6 images on pages 4, 6 and 8). Those can be extracted directly with `page.get_images()` / `get_image_bbox`.

## 4. How Answers and Solutions key to (Round, number)

### Answers (8 pages)

- Cover page.
- One or two pages per Round, each headed `Sprint Round`, `Target Round`, `Team Round` or `Countdown Round`.
- Entries are laid out in 2–3 columns as `N. ____value  unit`.
- Fractions are stacked: the numerator sits above the blank line.
- Coverage: 30 Sprint, 8 Target, 10 Team, 80 Countdown.
- The key excludes the Tiebreaker Round ("Answers to the Tiebreaker Round problems appear in the Tiebreaker Round Booklet"). That booklet is not on the site.

A 60-line position-based parser (page header gives the Round, an `N.` anchor gives the number, the spans to its right give the value, and spans above the line give a fraction numerator) recovered **114 of 128** answers exactly on the first try. Of the 14 misses:

- **12 are parser geometry bugs**: the right-hand column of Team, the tall fractions in Team 2 and 5, and Countdown numerators bleeding into the item above. These are fixable.
- **2 are not recoverable from text**: Sprint 25 `2√3` extracts as `2 3`, and Sprint 30 `3∛450` extracts as `3 3 450`. As in the problems, the radical is drawn as a vector.

Answer forms seen:

| Form | Examples |
|---|---|
| integer | `14` |
| comma-grouped integer | `18,050` |
| decimal | `38.5`, `275.35` |
| common fraction | `2/5`, `3/88` |
| π expression | `36π` |
| radical | `2√3`, `3∛450` |
| percentage unit | `4 (%)` |
| text answer | `Blue or B` (Countdown 80) |
| alternatives | `12 or 12.00` (Team 3, with `$` printed before the blank) |

Units are the same as in the problem's answer blank. In Countdown they are in parentheses.

### Solutions (9 pages)

- Cover page.
- Then a flowing Word document with one underlined heading per Problem: `Sprint 1` … `Sprint 30`, `Target 1` … `Target 8`, `Team 1` … `Team 10`. In the raw text the space is U+2007 (figure space). The regex `^(Sprint|Target|Team)\s+\d+$` on text lines finds exactly **48 headings: 30 Sprint, 8 Target, 10 Team**.
- **There are no Countdown solutions.**
- Use PyMuPDF's default reading order, not `sort=True`. Sorted mode jams the heading into the middle of the first paragraph.

Solution prose extracts well. The Cambria Math content is badly encoded, because of broken ToUnicode maps in Word's PDF export:

- Math italic letters are **doubled**: `𝑥𝑥` for *x*, `𝐴𝐴` for *A*. These can be repaired: collapse each pair and map the Mathematical Alphanumeric block to ASCII.
- **Bold final answers are corrupted beyond repair.** `14` extracts as `𝟏𝟏𝟏𝟏` (four MATHEMATICAL BOLD DIGIT ONE), `59` as `𝟓𝟓𝟓𝟓`, and `600` as `𝟔𝟔𝟔𝟔𝟔𝟔`. The answer key is the source of truth for answers anyway.
- Stacked fractions break across lines. Large radicals come out as the Sinhala letter `ඥ`. Superscripts flatten (`22𝑥𝑥` for 2^(2^x)).

## 5. Method comparison on a sample

Methods compared:

- **Text layer**: PyMuPDF text, equivalent to `pdftotext`.
- **Surya OCR**: the repo's service.
- **LLM vision**: pages rendered at 90–110 dpi and read by Claude (this agent). The vision answers were checked against the Answer key where possible, e.g. Sprint 4 gives 2/5, and Team 2's tallies (8 / 3 / 7 / 10) give 8/28 = 2/7. Both match the key.

The Surya service was **not reachable**:

- The app's `GET /api/v1/ocr/health` returns `503 {"status":"unhealthy","ocr_service":"unavailable"}`.
- `OCR_SERVICE_URL` points at `http://localhost:8000`, which refuses connections.
- The `ocr` service in `docker-compose.yml` is commented out.

Per the ticket it was not set up, so Surya was not tested. Note also that `src/services/ocrService.ts` posts single images to `${OCR_SERVICE_URL}/ocr` and has no math- or LaTeX-specific handling.

| Problem | What's hard | Text layer | LLM vision |
|---|---|---|---|
| Sprint 4 | spinner figure | prose exact; labels doubled (`4848 2121…`); spinner itself only as a crop | exact, incl. sector values 48, 21, 37, 15, 12 |
| Sprint 6 | `(12−♥)/3 = 1` | ♥ (vector) and fraction lost: `If 1, what is the value of ♥?` | exact |
| Sprint 10 | `V_sphere = (4/3)πr³` | garbled `Vsphere O °r` | exact |
| Sprint 17 | `a^b × c^d` | flattened `a b × c d` (recoverable via span flags) | exact |
| Sprint 23 | `√(6+2√5) = a+√b` | radicals lost: `6 + 2 5 … a + b` | exact |
| Sprint 28 | `√(75²+1)` | `75 2 + 1` | exact |
| Target 2 | trapezoid figure | prose and labels `15 in / 4 in / 21 in` fine | exact |
| Target 3 | coordinate graph | prose fine; tick labels interleave with prose | exact, reads A(2, 5) |
| Target 5 | `\|x + 2\| ≤ 6` | exact | exact |
| Target 8 | unit `units²` | prose exact; unit `units2` | exact |
| Team 2 | tally-mark table | **data lost** (tallies are vectors) | exact (8, 3 / 7, 10) |
| Team 4 | inline 1/2, 1/3 | fractions scattered onto other lines | exact |
| Team 6 | two-line unit | `years old` split across lines, but recoverable | exact |
| Team 10 | quadrilateral figure | prose fine; labels jumbled | exact |
| Countdown 2 | `2^10`, `12^3` | `210`, `123` (recoverable via span flags) | exact |
| Countdown 5 | `√(20√25)` | `20 25` | exact |
| Countdown 9 | `2^5 × 8^3 × 16^2 = 4^m` | flattened (recoverable via span flags) | exact |
| Countdown 26 | `22!/20!` | split: `22 !` on one line, `20 !` on the next | exact |
| Countdown 80 | ★ in text, graph figure | ★ missing; figure only as a crop | exact |

Summary of the scores:

- **Text layer**: boundaries 100%, prose near-perfect, math ~50% of math-bearing sample Problems usable as-is. It is good for segmentation, numbering, units and answer keys, and as a cross-check on vision output.
- **LLM vision**: 19/19 sample Problems exact, including figure data. Risks are hallucination, cost per page and non-determinism. Cross-check against the text layer's words (e.g. require high word overlap) and against the Answer key.
- **Surya**: untested (service down). It brings no clear benefit on born-digital PDFs, where the text layer already gives perfect plain text. Its value would only be math recognition, which would need its own evaluation.

## 6. Notes for the `crawled_data/` format and schema designers

- **Rounds and format** come from the cover pages. Store these as Round format defaults:
  - Sprint: 30 problems, 40 minutes, no calculator, individual.
  - Target: 8 problems in 4 pairs, 6 minutes per pair, calculator, individual.
  - Team: 10 problems, 20 minutes, calculator, team.
  - Countdown: 80 problems in a booklet; oral and head-to-head, so the cover gives no time limit.
- **Every Problem has a single answer blank.** No multi-part answers appear in 2025 Chapter, and Team Problems are ordinary single-answer Problems. The schema does not need multi-part answers for this Test. Other years may differ.
- **Answer** needs:
  - a display value, ideally LaTeX: radicals, fractions and π all occur;
  - an optional **unit string** taken from the blank: `cm²`, `ordered pairs`, `years old`, or a prefix `$`;
  - optional **alternates** (`12 or 12.00`, `Blue or B`).
  The "Forms of Answers" rules (Sprint PDF, page 8) are Competition-level guidance for self-grading, not per-Problem data.
- **Solutions are partial**: Sprint, Target and Team only, with none for Countdown. Solutions also contain raster figures. The format must allow a Problem with no solution.
- **Figures**: plan on a per-Problem image (figure crop, or the whole Problem crop as a fallback) next to the text, because some Problems carry their data only in the figure (Team 2 tallies, Sprint 4 spinner values, graphs).
- **Stable source ids**: the Drive file id per material, and the printed document code (`02-C25SPR`, `02-C25TEA`, `02-C25CDR`, `02-C25ANS`; Target and Solutions print none). Problem pages say "Copyright … 2024" while covers say 2025, so don't infer the year from footers.
- **Page structure** per problem PDF: a cover page (instructions, honor pledge, sponsors), then problem pages, then a trailing blank page. Sprint also has a "Forms of Answers" page last. Skip pages with no `N.` anchors.

## Reproduction sketch

```python
import re, pymupdf
doc = pymupdf.open("sprint.pdf")
for page in doc:
    words = page.get_text("words")
    anchors = sorted((w for w in words if w[0] < 60 and re.fullmatch(r"\d+\.", w[4])), key=lambda w: w[1])
    footer = min((w[1] for w in words if w[4] == "Copyright"), default=page.rect.height - 40)
    for i, a in enumerate(anchors):
        bottom = anchors[i + 1][1] - 6 if i + 1 < len(anchors) else footer - 4
        band = pymupdf.Rect(36, a[1] - 6, page.rect.width - 36, bottom)
        # grow band by drawing clusters centred in it, then:
        page.get_pixmap(dpi=150, clip=band).save(f"sprint-{a[4][:-1]}.png")
```
