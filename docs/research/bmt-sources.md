# BMT sources: what is published, and how extractable it is

Research for issue #51 (child of map #50). Run 2026-11-24. BMT here means the Berkeley Math Tournament (high school), not BmMT.

**Short answer.** Every BMT from 2012 to 2025 is on one official archive at `https://berkeley.mt/archives/bmt-<year>/`. Downloads are plain HTTPS with no auth. Every sampled PDF is born-digital pdfTeX in Computer Modern, one column on US Letter, with vector figures. The layout is much more uniform than MATHCOUNTS's. Since 2018 the "solutions" file restates each Problem and then gives an `Answer:` line, so the text layer alone segments the Problems and finds the Answers. The cheap first subset is **BMT 2018–2025 (8 Tests)**. The recommended pilot is **BMT 2025**.

No PDFs or problem text are in this repo. The samples were downloaded to `/tmp/bmt-samples/` and read with `python -I`. Only structure (counts, positions, file shapes) is recorded here.

## Sources

- **Index:** `https://berkeley.mt/archives/` lists every BMT and BmMT archive page. It also has per-Round pages (`/archives/bmt/guts-round/`, `individual-round/`, `power-round/`, and the "Historic" `team-round/`), which link to the same per-year files.
- **Per year:** `https://berkeley.mt/archives/bmt-<year>/` (2012–2025). Each page has a table of Round, Problems PDF and Solutions PDF, with relative links (`IS2016.pdf`, `general-problems.pdf`). Every linked PDF returned HTTP 200 `application/pdf` with no auth, cookies or redirects to a login. All 2012–2025 links were checked with HEAD requests.
- **Missing pages:** `bmt-2011`, `bmt-2026`, `bmt-2025-online` and `bmt-2024-online` all return 404. BMT 2026 was held on Nov 14, 2026 (news post of Nov 22, 2026), and its online sitting is on Dec 5, 2026, so 2026 isn't archived yet.
- **The site's own caveat:** "Note that problem styles may change throughout the years. Recent tests will be more representative of upcoming tournaments." (archives index).
- **No mirrors were needed.** The official archive is complete for what BMT publishes.

### Online sittings

There is **no separate archive for an online sitting**. 2020 was a single remote event (Oct 3–4, 2020). 2025's page links a `results-online.pdf` but no online-only tests.

The BMT 2026 Online event page says the online event runs the Power, Guts and Focus/General rounds a few weeks after the in-person event. It also says students "must not have competed in a prior iteration of BMT 2026, including the California version or any of our satellites." That rule implies the online sitting **reuses the in-person papers**. This is an inference: no Online paper was found to compare against.

**Implication for the map:** for now, no "BMT <year> Online" Test variant is needed.

## Per-year table

Rounds in **bold** are in scope (short answer). Power (proof-based) and Tiebreakers are listed for completeness only. File codes: `S` = solutions, `A` = answers, `Tb`/`TB` = tiebreaker. Problem counts come from text-layer anchors in the sampled files. "?" means not sampled.

| Test | Date | In-scope Rounds (Problems) | Also published | Answers / Solutions shape | Producer (sampled) |
|---|---|---|---|---|---|
| BMT 2012 | Apr 7 2012 | **Individual** (10), **Team**, **"Tournament"** (?) | Power | `XS2012.pdf`: Solutions only. Each is numbered `N.` with no restatement, and the final value is boxed inline. No separate key. | dvips + Ghostscript (problems), pdfTeX (solutions) |
| BMT 2013 | Mar 23 2013 | **Individual** (20), **Team**, **Analysis**, **Discrete**, **Geometry** | Power | `S` = Solutions, same shape as 2012 | pdfTeX |
| BMT 2014 | Mar 22 2014 | **Individual** (20), **Team**, **Analysis**, **Geometry** | Power (S) | `A` = **answer key only** ("INDIVIDUAL ROUND ANSWER KEY", 1–2 pages, `N.` + value). No Solutions. | pdfTeX; some pdftk-merged |
| BMT 2015 | Mar 7 2015 | **Individual** (20, **no Answers published**), **Team** (A), **Analysis** (S), **Geometry** (A) | Power; Individual/Analysis/Geometry Tiebreakers (no answers) | mixed `A` and `S` | pdfTeX; Quartz re-save |
| BMT 2016 | Mar 12 2016 | **Individual** (20), **Team** (15), **Analysis**, **Discrete**, **Geometry** | Power (S) | `A` = answer key only (sampled Individual: 1 page) | pdfTeX; pdftk-merged problems |
| BMT 2017 | Mar 12 2017 | **Individual** (20), **Team**, **Analysis**, **Discrete**; **Geometry: answer key only, no Problems PDF** | Power (S) | `A` = answer key only | pdfTeX |
| BMT 2018 | Mar 18 2018 | **Focus: Algebra** (10), **Calculus**, **Combinatorics**, **Geometry**, **Number Theory**; **Team** | Power; a Tiebreaker for each Focus subject | `A` = **Problem restated, then `Answer:` and `Solution:`** (5 pages for Algebra). No Individual/General test. | pdfTeX |
| BMT 2019 | Apr 7 2019 | **Individual**, **Team**, **Algebra**, **Discrete**, **Geometry** | Power; Tiebreakers | `*-solutions.pdf`, restated + `Answer:` | ? (presumed pdfTeX) |
| BMT 2020 | Oct 3–4 2020 (remote) | **Individual** (25), **Team**, **Algebra**, **Calculus**, **Discrete**, **Geometry** | Power; Tiebreakers | restated + `Answer:` | pdfTeX ("LaTeX with hyperref") |
| BMT 2021 | Nov 20 2021 | **General**, **Algebra**, **Calculus**, **Discrete**, **Geometry**, **Guts** | Power; Tiebreakers | restated + `Answer:` | ? (presumed pdfTeX) |
| BMT 2022 | Nov 5 2022 | **General** (25), 4 Focus, **Guts** | Power; Tiebreakers | restated + `Answer:` | pdfTeX |
| BMT 2023 | Nov 4 2023 | **General**, 4 Focus, **Guts** | Power; Tiebreakers | restated + `Answer:` | ? (presumed pdfTeX) |
| BMT 2024 | Nov 2 2024 | **General**, 4 Focus, **Guts** | Power (no Tiebreakers published) | restated + `Answer:` | ? (presumed pdfTeX) |
| BMT 2025 | Nov 8 2025 | **General** (25), **Algebra**, **Calculus**, **Discrete**, **Geometry** (10), **Guts** (27) | Power; Tiebreakers | restated + `Answer:` | pdfTeX; problem files pdftk-merged with a cover page |

### How the Rounds changed

- **2012:** Individual, Team, "Tournament", Power.
- **2013–2017:** Individual, Team, Focus subjects and Power. The Focus subjects were Analysis, Discrete and Geometry; 2014 and 2015 had no Discrete.
- **2018:** Focus only (five subjects) plus Team, with no Individual test.
- **2019–2020:** Individual, Team and Focus.
- **2021 onwards:** General, four Focus subjects (Algebra, Calculus, Discrete, Geometry) and Guts. The Team round went away; the archive lists it as "Historic".
- **Guts is published only from 2021.** The `/archives/bmt/guts-round/` page lists 2021–2025 only.
- **Problem counts:** a Focus test has 10 Problems (2018, 2025). Individual or General has 20 (2013–2017) or 25 (2020+). 2025 Guts has 27, in 9 sets of 3. A current Test is about 25 + 4×10 + 27 = **92 short-answer Problems**.

### File names

- **2012–2017:** codes such as `IS2016.pdf` / `IS2016A.pdf`, `AnaS2014.pdf` and `GeoS2015Tb.pdf`.
- **2018:** a one-off scheme (`ALSP18.pdf`, `ALSP18A.pdf`, `ALSP18TB.pdf`).
- **2019 onwards:** uniform names (`<round>-problems.pdf` / `<round>-solutions.pdf`, `<round>-tiebreaker-…`).

The crawler should read the per-year table rather than guess names, because the cells say which column, Problems or Solutions, each file belongs to. Some cells are empty, for example 2015 Individual Solutions and 2017 Geometry Problems.

## Extractability

Sampled files (old, middle and recent):

- **2012:** Individual problems and solutions.
- **2013:** Individual solutions.
- **2014:** Individual and Analysis answer keys.
- **2015:** Individual problems and Team answer key.
- **2016:** Individual problems and answer key; Team problems.
- **2017:** Individual and Geometry answer keys.
- **2018:** Algebra problems and solutions.
- **2020:** Individual problems and solutions.
- **2022:** General problems and solutions.
- **2025:** General problems and solutions, Geometry problems, Guts problems and solutions.

### Born-digital, LaTeX

- **No scans.** Every sample is LaTeX output: pdfTeX, or dvips plus Ghostscript for 2012 problems. Some files were later merged with pdftk or re-saved by Quartz.
- **Fonts:** Computer Modern throughout (CMR10, CMMI10, CMSY10, CMEX10, MSAM/MSBM).
- **No U+FFFD anywhere.**
- **Images:** the only raster image is the cover-page logo in 2025 problem files.

### Layout

- **Page:** one column, US Letter (612×792 pt).
- **Header:** a running header such as "BMT 2025 · General Test · November 8, 2025" (2018 onwards).
- **Cover page:** 2021+ problem files open with a cover or instructions page (time limit, answer-format rules) before Problem 1.
- **Anchors:** each Problem is an `N.` line at the left margin.
  - x ≈ 72 pt in 2012 and 2018–2025; two-digit numbers outdent to x ≈ 66.5 in 2025 Guts.
  - x ≈ 80–85 pt in 2013–2017.
  - Anchor font: CMR10 at **10.9 pt** (10.0 in 2012).
- **Guts:**
  - One set per page under a `Set k` heading, with 3 Problems per set.
  - Page 1 holds the scoring rules (points per question rise from 10 in Set 1 to 25 in Set 9).
  - Set 9 is **estimation**. Each estimation Problem prints its own scoring formula, for example a `round(25·exp(…·max(E/A, A/E)…))` shape. That formula's large delimiters come through the text layer as control characters.

### Text-layer check (an `extract.py`-style pass)

The throwaway checker lived in `/tmp/bmt-scripts/`, not in the repo. It took sequential `N.` anchors with x < 90 and split Problems into bands between anchors. It counted vector-drawing clusters of at least 30×20 pt inside each band, and in solutions files it took the first `Answer` line after each anchor.

| File | Problems found | Contiguous | Figures detected | `Answer:` lines | Answer on one clean line |
|---|---|---|---|---|---|
| 2025 General | 25 | yes | 3 | 25/25 | 19 |
| 2025 Guts | 27 | yes | 4 | 27/27 | 19 |
| 2025 Geometry | 10 | yes | 3 | (not sampled) | |
| 2022 General | 25 | yes | 4 | 25/25 | 16 |
| 2020 Individual | 25 | yes | 2 | 25/25 | 24 |
| 2018 Algebra | 10 | yes | 0 | 10/10 | 9 |
| 2016 Individual | 20 | yes | 0 | n/a: the key is `N. value` with no `Answer:` (20/20 `N.` anchors in the key) | |
| 2016 Team | 15 | yes | 0 | | |
| 2015 Individual | 20 | yes | 0 | none published | |
| 2012 Individual | 10 | yes | 0 | n/a: the answer is boxed inside the solution prose | |

**Findings:**

- **Segmentation is perfect in every sampled year**, with no layout variants of the kind MATHCOUNTS 2010–2011 had. The solutions file restates every Problem under the same `N.` anchor, so it pairs one-to-one with the problems file.
- **The Answer key (2018+) is keyed by anchor.** About 65–95% of Answers sit on one clean line. The rest are stacked fractions or radicals spread over several text lines, about 1 in 4 on recent General and Guts. Those need vision, as in MATHCOUNTS.
- **Answer keys are not always a single value.**
  - The 2016 key has a set-valued answer (three values, comma-separated).
  - The 2014 Analysis key has `x = 0, log2 3`.
  - The 2016 key has an `A or B` alternative (`… or 24`).
  - These feed the "Answers that aren't a single value" question in #50.
- **How math reads in the text layer:**
  - **Prose is clean**, apart from ligatures (`ﬀ`) that need normalising.
  - **Superscripts flatten** (`5^2 + 8^2` reads as `52 + 82`), the same as MATHCOUNTS.
  - **Radicals:** `√` comes through as a glyph, but the vinculum is a drawing, so the radicand's extent is lost.
  - **Fractions:** stacked fractions split into separate lines.
  - **Big delimiters:** CMEX big delimiters become control characters (`\x10`–`\x13`).
  - **Overall:** vision is still needed for the final LaTeX, but the text layer is a better cross-check than MATHCOUNTS's InDesign/Word output, because the glyph mappings are standard TeX.
- **Figures** are vector drawings (TikZ/Asymptote style) with text-layer labels, centred below the Problem text. The cluster heuristic finds them; the MATHCOUNTS crop-and-grow approach should carry over.

### What `scripts/mathcounts/extract.py` would need for BMT

| Change | Why |
|---|---|
| Anchor margin `x < 60` → about `x < 90` | BMT anchors sit at x ≈ 66–85 pt. |
| Anchor size `>= 11` → about `>= 9.5` | BMT anchors are 10.9 pt (10.0 in 2012), so the current filter rejects all of them. |
| Anchors must be sequential | Solutions prose contains `N.`-shaped lines (`144.`, `1000.`), and 2021+ cover pages contain stray numbers. Accepting only the next expected number removes them. |
| Skip the cover or instructions page | 2021+ problem files. |
| Answers from `Answer:` lines in the solutions file | 2018+, instead of a separate key PDF. For 2014–2017, parse the `N. value` key instead, which is close to the MATHCOUNTS answer parser. |
| Rounds from the archive table, not fixed names | Round names and file names change across years. |
| Guts: record the set number and points per Problem; mark Set 9 as estimation | Feeds the #50 Guts questions. Each estimation Problem's scoring formula is part of its text. |

## Recommendations

### Cheap first subset: BMT 2018–2025 (8 Tests)

- **Why these years:** Problems and Solutions come in pairs, with an `Answer:` line after each restated Problem, so Answers and Solutions are both available and anchor-keyed. The text layer segments every sampled Problem.
- **Rounds by year:**
  - 2021–2025: General, Algebra, Calculus, Discrete, Geometry, Guts (about 92 Problems each).
  - 2018: five Focus subjects and Team.
  - 2019–2020: Individual, Team and Focus.
- **Second tier, BMT 2014, 2016, 2017:** Answers only, through a short `N. value` key, with no Solutions. Clean, but these fall under the "Incomplete Tests" question. 2017 Geometry has no Problems PDF, so drop that Round.
- **Third tier:**
  - **2012–2013:** Solutions only, with the Answer boxed in prose, so vision would have to pull the Answer from the solution text.
  - **2015:** mixed. Individual has no Answers, so that Round is out under "Answers required". Team, Analysis and Geometry are usable.
- **Not yet available:** BMT 2026 is not archived yet. Recheck after the Dec 5, 2026 online sitting.

### Pilot Test: BMT 2025

- **Most representative.** It is the most recent Test, in the current format (General + four Focus subjects + Guts), and the site says recent Tests best represent the tournament.
- **Text layer checks out.** It passed with 25/25 General and 27/27 Guts Problems and Answers.
- **It covers the hard cases.**
  - Vector figures (General, Geometry).
  - Stacked-fraction and radical Answers.
  - The Guts set structure.
  - Estimation Problems (Set 9), which answer the Guts and estimation questions left open in #50.
- **Expected size:** 6 Rounds, about 92 Problems.
- **Files:** 12 PDFs, from `https://berkeley.mt/archives/bmt-2025/{general,algebra,calculus,discrete,geometry,guts}-{problems,solutions}.pdf`.
- **Fallback:** if a shorter pilot is wanted, BMT 2022 is the same format without the pdftk cover page.

## Sources

- BMT archive index: https://berkeley.mt/archives/
- Per-year archive pages: https://berkeley.mt/archives/bmt-2012/ through https://berkeley.mt/archives/bmt-2025/
- Guts Round archive (2021–2025 only): https://berkeley.mt/archives/bmt/guts-round/
- BMT 2026 Online event page (online format and eligibility): https://berkeley.mt/events/bmt-2026-online/
- BMT 2026 score-report news post (2026 sitting held, not yet archived): https://berkeley.mt/news/bmt-2026-thanks-and-score-reports/
- PDF metadata, fonts, anchors and `Answer:` lines: read directly from the sampled PDFs listed above with PyMuPDF.
