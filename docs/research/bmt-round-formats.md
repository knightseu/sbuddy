# BMT Round formats, 2012–2025

Research for issue #52 (child of map #50). Vocabulary follows `GLOSSARY.md`: **Competition**, **Test**, **Round**, **Round format**, **Answer**. BMT here means the Berkeley Math Tournament (high school), not BmMT.

Every claim carries a source tag. **[P…]** tags are primary sources: berkeley.mt pages, the official BMT site as archived by the Wayback Machine, and the headers of the official test PDFs. The sources are listed at the end. Where the website and a test PDF disagree, the PDF wins, because the archived logistics pages were often not updated between years (noted in each case below).

## Answer in one paragraph

BMT's format is **not** stable the way MATHCOUNTS's is. It falls into three eras:

1. **2012–2017:** Individual, Team, subject "Focus" tests, and Power.
2. **2018–2019:** a transition. 2018 dropped the Individual test and split Focus into five subjects; 2019 brought the Individual test back.
3. **2020–2025:** the current format. A 25-problem General test, four 10-problem Focus tests (Algebra, Calculus, Discrete, Geometry), a 27-problem Guts round in 9 sets of 3, and Power. In 2020 the General and Guts tests were still named "Individual" and "Team".

Some things never change:

- Calculators are banned in every year and every Round.
- Every short-answer Round has one exact, simplified Answer per Problem.

The only Answers that are not a single value are:

- the proof problems inside the 2013–2015 Focus tests;
- the Guts **Set 9 estimation problems**, from 2020 on.

From 2023 there is also an online sitting. It uses **the same problem set** as the in-person sitting, so it publishes nothing of its own. BMT 2020 and 2021 were online-only: they are the year's only Test, and their PDFs carry online-specific instructions.

Competition defaults plus per-Test overrides in `tests.metadata` are enough, with three provisos:

- the defaults should describe the 2020–2025 era;
- 2012–2019 Tests should carry their own full `rounds` block rather than override a default;
- the format needs a "set" time-limit scope, and two per-Problem facts belong on the Problem rather than the Test: Guts point values and estimation scoring.

## Which Rounds each Test has (from the official archive)

The archive page for each year lists these Rounds and materials [P1]. Power and the Tiebreakers are out of scope for the map (#50). They are listed here only to complete the picture.

| Year (date) | Short-answer Rounds published | Out-of-scope | Materials gaps |
|---|---|---|---|
| 2012 (Apr 7) | Individual, Team, Tournament | Power | |
| 2013 (Mar 23) | Individual, Team, Focus: Analysis, Discrete, Geometry | Power | |
| 2014 (Mar 22) | Individual, Team, Focus: Analysis, Geometry | Power | Answer keys only ("…A.pdf"), with no worked solutions except write-ups of the Focus proofs |
| 2015 (Mar 7) | Individual, Team, Focus: Analysis, Geometry | Power; Individual/Analysis/Geometry Tiebreakers | **Individual has no answers or solutions file**; Tiebreakers have no solutions; Team and Geometry have answer keys only |
| 2016 (Mar 12) | Individual, Team, Focus: Analysis, Discrete, Geometry | Power | Answer keys only |
| 2017 (Mar 12) | Individual, Team, Focus: Analysis, Discrete, Geometry | Power | **Geometry has only its answer key, no problems PDF**; answer keys only |
| 2018 (Mar 18) | Team, Focus: Algebra, Calculus, Combinatorics, Geometry, Number Theory | Power; a Tiebreaker for each Focus | **No Individual test** |
| 2019 (Apr 7) | Individual, Team, Focus: Algebra, Discrete, Geometry | Power; Individual and Focus Tiebreakers | No Calculus |
| 2020 (Oct 3, online) | "Individual" (= General), "Team" (= Guts), Focus: Algebra, Calculus, Discrete, Geometry | Power; Tiebreakers | |
| 2021 (Nov 20, online) | General, Guts, Focus ×4 | Power; Tiebreakers | |
| 2022 (Nov 5) | General, Guts, Focus ×4 | Power; Tiebreakers | |
| 2023 (Nov 4) | General, Guts, Focus ×4 | Power; Tiebreakers | |
| 2024 (Nov 2) | General, Guts, Focus ×4 | Power | No Tiebreakers published |
| 2025 (Nov 8) | General, Guts, Focus ×4 | Power; Tiebreakers | |

Notes:

- The archive itself says that "BMT 2020's Individual and Team Rounds are equivalent to the General and Guts rounds in recent BMTs, respectively" [P1]. Its by-round index groups the 2020 Team round with the old Team rounds, not with Guts [P2]. The content says otherwise: the 2020 "Team Round" PDF is a 9-set Guts round with the same point table as 2021 [P5].
- "We no longer administer a Team Round at BMT" [P2]. The old Team round (10–20 problems on one sheet) last ran in 2019.
- The archive has no BMT 2026 page yet. BMT 2026 was held on Nov 14, 2026, and BMT 2026 Online is on Dec 5, 2026 [P3].
- All 2012–2025 PDFs are born-digital, and PyMuPDF extracts text from all of them; none are scans.

## Round formats by year

Problem counts are from the PDFs: the stated count where there is one, otherwise the highest problem number. Times come from the PDF header where it states one (2017 on), otherwise from the archived website for that season. "Indiv." means individual. Calculator: **none, in every Round of every year** (see the next section).

### 2012–2017 (Individual / Team / Focus era)

| Year | Round | Problems | Time | Who | Structure / notes |
|---|---|---|---|---|---|
| 2012 | Individual | 10 [P5] | not published | Indiv. | |
| 2012 | Team | 10 [P5] | not published | Team | |
| 2012 | Tournament | 42 = 7 blocks × 6 [P5] | not published | Team (head-to-head) | Blocks are labelled Round 1, 2, 3, 4, 4 (two different sets), Championship and Consolation, which suggests an elimination bracket. No rules page survives. |
| 2013 | Individual | 20 | 80 min [P6] | Indiv. | Each question is "weighted according to the number of students who answered it correctly" [P6]. |
| 2013 | Team | 10 | 20 min [P6] | Team | One answer sheet per team [P6]. |
| 2013 | Focus (Analysis, Discrete, Geometry) | 10 short answer + 2 proofs (P1, P2) [P5] | 60 min [P6] | Indiv. | "Up to 10 short answer questions and 1–2 proof questions". Each test was preceded by a 20-minute guest lecture [P6]. |
| 2014 | Individual | 20 [P5] | 80 min [P7: Oct 2014 page] | Indiv. | |
| 2014 | Team | 20 [P5] | 40 min [P7] | Team | |
| 2014 | Focus (Analysis, Geometry) | 10 + 2 proofs [P5] | 60 min [P7] | Indiv. | "Each student takes exactly one exam" [P7]. |
| 2015 | Individual | 20 [P5] | 80 min [P7] | Indiv. | |
| 2015 | Team | 20 [P5] | 40 min [P7] | Team | |
| 2015 | Focus (Analysis, Geometry) | 10 + 2 proofs [P5] | 60 min [P7] | Indiv. | One Focus test per student [P7]. |
| 2016 | Individual | 20 [P5] | 80 min [P7] | Indiv. | |
| 2016 | Team | **15** [P5] | 40 min [P7] | Team | The 2016 website still said "20 questions … 2 proof questions" [P7]. The 2016 PDFs have 15 Team problems and no proofs in Focus, so the page was stale. |
| 2016 | Focus (Analysis, Discrete, Geometry) | 10 [P5] | 60 min [P7] | Indiv. | No proof problems from 2016 on. |
| 2017 | Individual | 20 | 80 min [P5] | Indiv. | PDF: "This test contains 20 short answer questions … No calculators." |
| 2017 | Team | 15 | 40 min [P5] | Team of 6 | "you work in teams of six to solve 15 short answer questions" [P5]. |
| 2017 | Focus (Analysis, Discrete, Geometry) | 10 | 60 min [P5] | Indiv. | Geometry problems are missing from the archive. |

### 2018–2019 (transition)

| Year | Round | Problems | Time | Who | Structure / notes |
|---|---|---|---|---|---|
| 2018 | Focus (Algebra, Calculus, Combinatorics, Geometry, Number Theory) | 10 each | 60 min [P5] | Indiv. | Five subjects, the only year with more than four. |
| 2018 | Team | 15 | 40 min [P5] | Team | |
| 2018 | (no Individual) | | | | 2019: "Due to popular demand, the individual round has returned!" [P8]. |
| 2019 | Individual | 20 | 90 min [P5][P8] | Indiv. | "will test understanding in all three of the focus topics" [P8]. |
| 2019 | Focus (Algebra, Discrete, Geometry) | 10 each | 60 min [P5][P8] | Indiv. | Students sat both a Focus test and the Individual test. Team score was weighted Focus 25%, Individual 25%, Team 20%, Power 30% [P8]. |
| 2019 | Team | 15 | 40 min [P5][P8] | Team (up to 6) | |

### 2020–2025 (General / Focus / Guts era)

| Year | Round | Problems | Time | Who | Structure / notes |
|---|---|---|---|---|---|
| 2020–2025 | General ("Individual" in 2020) | 25 | 90 min [P5] | Indiv. | |
| 2020–2025 | Focus: Algebra, Calculus, Discrete, Geometry | 10 each | 60 min [P5] | Indiv. | From 2021 on, a student takes **either General or two Focus tests** [P3][P11]. A General score counts half as much as a two-Focus combination [P3]. |
| 2020–2021 | Guts ("Team" in 2020) | 27 = 9 sets × 3 | **60 min** [P5] | Team | Set k+1 is handed out only after set k is submitted, and there is no going back. Sets 1–8 are short answer; Set 9 is estimation [P5]. |
| 2022–2025 | Guts | 27 = 9 sets × 3 | **75 min** [P5][P3] | Team (4–6 recommended) | Same rules, with a live scoreboard [P3]. The 2022 web page says 60 min in one place and 90 in its summary table; the PDF's 75 min wins. |

Guts point values per question, by set [P5]:

| Set | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 (estimation) | Max total |
|---|---|---|---|---|---|---|---|---|---|---|
| 2020–2022 | 10 | 11 | 12 | 13 | 14 | 16 | 18 | 20 | 25 | 417 |
| 2023–2025 | 10 | 11 | 12 | 13 | 14 | 16 | 18 | **21** | 25 | 420 |

Team score weights (in person): Power 30%, Individual Round (General/Focus) 40%, Guts 30% [P3][P11]. Online: Individual 60%, Guts 40%, with Power ranked separately [P3].

## Calculator and answer rules

- **No calculators, ever.** This is stated in every PDF header from 2017 to 2025 ("No calculators.") [P5], and on the website for 2013 [P6], 2015–2017 [P7], 2019 [P8], 2022 [P11] and now [P4]. Since 2024 the PDFs add "Protractors, rulers, and compasses are permitted" [P5]. Graph paper is banned [P4].
- Answers must be "exact and simplified", and there is no partial credit except on Power [P12]. Format rules (lowest terms, radicals simplified, π allowed, exact decimals allowed) are printed in the PDF header from 2024 [P5][P12].
- **2020 only (online):** "All answers are positive integers" (header of every 2020 short-answer test) [P5]. This is the one year the answer domain was restricted. 2021, also online, went back to "simplest form" [P5].

## Answers that are not a single value

| Kind | Where | Count | What it looks like |
|---|---|---|---|
| **Proof** | 2013 Focus (Analysis, Discrete, Geometry); 2014 and 2015 Focus (Analysis, Geometry) | 2 per Focus test (labelled P1, P2), so 14 problems in all | Proof problems [P5]. The rules: "10 short answer questions and 2 proof questions" [P7]. There is no single Answer; the official solution is the proof. |
| **Estimation, scored by closeness to an exact Answer** | Guts Set 9 (problems 25–27), 2020–2025 | up to 3 per year | Each problem prints its own scoring formula in E (the submission) and A (the true answer), for example linear decay max(0, 25 − k\|A − E\|), a ratio min(A/E, E/A)^k, or an exponential [P5]. There is a single true Answer A; only the scoring is unusual. Some are worded as ordinary "compute" problems but are still scored by closeness (2021 #27, 2025 #27). |
| **Open choice: many answers earn full credit** | Guts 2024 #26 | 1 | The team submits a parameter of its own choosing. The score depends on a quantity N that the parameter produces, and it peaks at a target value of N [P5]. Every parameter that hits the target is fully correct, so the Answer is a description, not a value. |
| **Crowd-dependent: no fixed Answer** | Guts 2020 #25, 2022 #27 | 2 | Teams submit a number, and the score depends on every team's submission: a unique-number game in 2020, and a function of the sum of all teams' submissions in 2022 [P5]. There is nothing to reveal except the outcome. |
| **Several values in one Answer** | Rare, mostly 2012–2017 (e.g. 2014 Analysis #1, whose key lists two values; 2014 Analysis #10, an ordered triple; 2015 Geometry #1, all possible values) | a handful per year at most | Still one Answer string (a tuple or a list). This fits the existing Answer + alternatives. |

There are no multi-part short-answer Problems: none of the Team, Guts, General or Focus PDFs has (a)/(b) sub-questions [P5]. Multi-part questions exist only in Power (out of scope). Tiebreakers (out of scope) are scored by correctness and then submission time [P5].

## In-person vs online

| Sitting | Years | Problems | Format differences |
|---|---|---|---|
| Online-only main event | 2020 (Oct 3–4), 2021 (Nov 20–21) | The year's only set | The website says "BMT 2020 Online" and "BMT 2021 Online: November 20 & 21, 2021" [P9][P10]. The 2020 in-person BMT (Apr 11) was cancelled for COVID-19 [P9]. In 2020 every answer was a positive integer and Power lasted "1 Week" [P5]. The 2021 headers drop the answer-sheet sentence, because answers were submitted online [P5]. Round counts and Guts structure match the in-person years, apart from Guts being 60 min instead of 75. |
| In-person plus a separate online sitting | 2023 (online Jan 20, 2024), 2024 (online Dec 7, 2024), 2025 (online Dec 6, 2025), 2026 (online Dec 5, 2026) | **The same problem set as in person** | "The online tournament uses the same problem set as the in-person tournament, so students who competed in person are not eligible to compete online" [P4]. The 2023 Online page also bars anyone who sat "a prior iteration of BMT 2023" [P3]. Power is asynchronous and ranked separately, and Individual/Guts weights change to 60/40 [P3]. Round counts and times are the same (General 25/90, Focus 10/60, Guts 27/75) [P3]. The archive publishes one problem set per year, with a separate "Contest Results (Online)" file only [P1]. |
| In-person plus satellites / informal rerun | 2022 ("various satellite tournaments and an informal, online rerun") [P11], and China results every year from 2020 on [P1] | Not published separately | |

This matters for the map's Test identity note ("a separate online sitting … is its own Test with variant Online"). No year has online-only problems after 2021, so an "Online" Test would duplicate the in-person Test's Problems. Recommendation: **one Test per year**. For 2020 and 2021, record `variant: "Online"` or a metadata flag, because the whole Test was online. Do not create separate Online Tests for 2023 on.

## Does "Competition defaults + per-Test overrides in `tests.metadata`" suffice?

**Yes, with adjustments.** The MATHCOUNTS pipeline writes a full `metadata.rounds` block per Test, filled from a constant `FORMATS` table (`scripts/mathcounts/init_review.py`). That pattern carries over:

1. **Defaults = the 2020–2025 era.** `general` {25, 90 min, round scope, no calculator, individual}; `algebra` / `calculus` / `discrete` / `geometry` {10, 60 min, individual}; `guts` {27, 75 min, team, `time_limit_scope: "round"`, `group_size: 3`, `groups: 9`}.
2. **Per-Test overrides are real and frequent:**
   - Guts is 60 min in 2020–2021.
   - 2020's Round names differ (Individual / Team), and its `answer_domain` is positive integers.
   - Before 2020, almost every year needs its own block: Round sets change (Analysis → Algebra + Calculus; Combinatorics + Number Theory → Discrete; Individual absent in 2018; the 2012 Tournament round), and problem counts and times change too.

   It is simpler to give each pre-2020 Test its complete `rounds` block than to express it as a diff.
3. **Round keys should be per subject** (`analysis`, `combinatorics`, `number-theory` as well as the four current ones). Each Focus subject is its own Round, as the map decided. No Competition-wide list of Focus subjects holds across years.
4. **Guts needs "sets of 3, released sequentially, whole round timed".** MATHCOUNTS Target used `time_limit_scope: "group"` + `group_size: 2` for separately timed pairs. Guts sets are grouped but not timed separately, so record `group_size: 3` with `time_limit_scope: "round"`.
5. **Point values belong on the Problem, not the Test.** `test_problems.points` already exists (INTEGER): 10, 11, … 25 by set. Alternatively, put a per-set `points` list in the Round format; either works, but the Problem column is free and needs no new structure.
6. **Estimation and other non-value Answers are per-Problem facts.** Put an `answer_kind` in `test_problems.metadata`, one of `exact` (default), `estimation`, `open` (2024 #26) or `crowd` (2020 #25, 2022 #27). The scoring rule stays in the problem text, which already prints it. Crowd problems have no Answer to reveal. The 14 proof problems (2013–2015 Focus P1/P2) need either `answer_kind: "proof"` with the Solution as the reveal, or exclusion, like Power.
7. **Who-takes-what is administration, not format.** Facts such as "General or two Focus tests", "one Focus test per student" (2014–2017) and "Focus and Individual" (2019) are not needed for the viewer. This mirrors the MATHCOUNTS finding that Countdown's official status was administration, not format.

## Sources

Primary, current site (fetched 2026-11-24):

- **[P1]** BMT archive index and per-year pages: https://berkeley.mt/archives/ and https://berkeley.mt/archives/bmt-2012/ … https://berkeley.mt/archives/bmt-2025/
- **[P2]** Archive by round: https://berkeley.mt/archives/bmt/individual-round/, …/guts-round/, …/team-round/ ("We no longer administer a Team Round at BMT"), …/power-round/
- **[P3]** Event pages: https://berkeley.mt/events/bmt-2026/, https://berkeley.mt/events/bmt-2026-online/, and the same paths for bmt-2023, bmt-2023-online, bmt-2024, bmt-2024-online, bmt-2025, bmt-2025-online (Contest Format, Round & Scoring Summary, Tiebreakers)
- **[P4]** FAQ: https://berkeley.mt/faqs/ (calculators; "the online tournament uses the same problem set as the in-person tournament")
- **[P5]** Official test PDFs, header and instructions text, e.g. https://berkeley.mt/archives/bmt-2025/guts-problems.pdf, https://berkeley.mt/archives/bmt-2017/TS2017.pdf, https://berkeley.mt/archives/bmt-2020/team-problems.pdf (all short-answer problem and answer PDFs for 2012–2025 were read)
- **[P12]** Acceptable answer formats: https://berkeley.mt/assets/answer-formats.pdf

Primary, archived official site (Wayback Machine):

- **[P6]** Rules, spring 2013: https://web.archive.org/web/20130226120021/http://bmt.berkeley.edu/rules/
- **[P7]** Logistics: https://web.archive.org/web/20141022010505/http://bmt.berkeley.edu/logistics/, https://web.archive.org/web/20150211222146/http://bmt.berkeley.edu/logistics/, https://web.archive.org/web/20160215031623/http://bmt.berkeley.edu/logistics/, https://web.archive.org/web/20170222192406/http://bmt.berkeley.edu/logistics/ (the text was often carried over between years; see the 2016 note)
- **[P8]** BMT 2019 logistics: https://web.archive.org/web/20190209224623/https://bmt.berkeley.edu/logistics_bmt/
- **[P9]** Announcements, 2020 (cancellation of spring 2020; BMT 2020 Online): https://web.archive.org/web/20200919234121/https://bmt.berkeley.edu/announcements/
- **[P10]** Home, 2021 ("BMT 2021 Online: November 20 & 21, 2021"): https://web.archive.org/web/20211104083137/https://bmt.berkeley.edu/home/
- **[P11]** BMT 2022 page: https://web.archive.org/web/20221018144721/https://www.ocf.berkeley.edu/~bmt/bmt-2022/

Not found: no rules page for spring 2012 or spring 2018 is archived, so 2012 times and the 2018 participation rules are unknown beyond what the PDFs say.
