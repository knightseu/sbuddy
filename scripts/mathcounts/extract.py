"""Extract a MATHCOUNTS Test's PDFs into a draft for review.

Usage (PyMuPDF is pulled in by uv, nothing is installed globally):

    uv run --with pymupdf python -I scripts/mathcounts/extract.py \
        crawled_data/mathcounts/_sources/2025-chapter \
        crawled_data/mathcounts/_work/2025-chapter

The source directory holds sprint.pdf, target.pdf, team.pdf, countdown.pdf,
answers.pdf and solutions.pdf (any may be missing). The work directory gets:

- crops/<round>-NN.png      the whole Problem band, for the vision pass
- figcrops/<round>-NN.png   figure-only crop, where a figure was detected
- pages/<name>-pP.png       rendered answer and solution pages
- solution-images/          raster images embedded in the Solutions PDF
- draft.json                text-layer reading of every Problem, answer and
                            solution, plus figure detection

The text layer is used for segmentation, numbering, units and the answer key
(see docs/research/mathcounts-2025-chapter-pdf-extraction.md). Its math is
lossy, so draft.json is a cross-check for the vision pass, not final content.
"""

import json
import re
import sys
from pathlib import Path

import pymupdf

ROUNDS = ["sprint", "target", "team", "countdown"]
ANCHOR = re.compile(r"^(\d+)\.")
CROP_DPI = 150
FIG_DPI = 200


def spans_of(page):
    """Non-blank spans; each is tagged with the length of its whole line,
    so figure labels (short, isolated lines) can be told apart from prose."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            line_len = len("".join(s["text"] for s in line["spans"]).strip())
            for s in line["spans"]:
                if s["text"].strip():
                    s["line_len"] = line_len
                    out.append(s)
    return out


def join_split_anchors(spans):
    """Merge an anchor split into a digit span and a "." span, as in 2014
    National Team 1 ("1" + ".   ")."""
    out = []
    for s in spans:
        prev = out[-1] if out else None
        if (prev and re.fullmatch(r"\d+", prev["text"].strip()) and s["text"].startswith(".")
                and abs(s["bbox"][1] - prev["bbox"][1]) < 2 and 0 <= s["bbox"][0] - prev["bbox"][2] < 1):
            out[-1] = dict(prev, text=prev["text"] + s["text"],
                           bbox=tuple(pymupdf.Rect(prev["bbox"]) | pymupdf.Rect(s["bbox"])))
        else:
            out.append(s)
    return out


def dedupe(spans):
    seen, out = set(), []
    for s in spans:
        key = (s["text"], tuple(round(v) for v in s["bbox"]))
        if key not in seen:
            seen.add(key)
            out.append(s)
    return out


def span_text(spans):
    """Rebuild reading-order text; small raised spans become ^{...}."""
    spans = sorted(spans, key=lambda s: (round(s["bbox"][1] / 6), s["bbox"][0]))
    parts, last_y = [], None
    for s in spans:
        y = round(s["bbox"][1] / 6)
        if last_y is not None and y != last_y:
            parts.append("\n")
        last_y = y
        t = s["text"].replace(" ", "").replace("\t", " ")
        if s["size"] < 8 and t.strip():
            parts.append("^{" + t.strip() + "}")
        else:
            parts.append(t)
    return re.sub(r"[ ]+", " ", "".join(parts)).strip()


def drawing_clusters(page, gap=8):
    """Cluster vector drawings, ignoring page-sized frames and hairline rules."""
    rects = []
    for d in page.get_drawings():
        r = d["rect"]
        if r.width > page.rect.width * 0.8 or r.height > page.rect.height * 0.8:
            continue
        if r.x0 > page.rect.x1 or r.x1 < 0 or r.y0 > page.rect.y1 or r.y1 < 0:
            continue  # off-page artwork (2020 State Target 5)
        rects.append(pymupdf.Rect(r))
    clusters = []
    for r in rects:
        merged = True
        cur = pymupdf.Rect(r)
        while merged:
            merged = False
            for c in clusters:
                grown = pymupdf.Rect(c.x0 - gap, c.y0 - gap, c.x1 + gap, c.y1 + gap)
                if grown.intersects(cur):
                    cur |= c
                    clusters.remove(c)
                    merged = True
                    break
        clusters.append(cur)
    return clusters


def is_figure(c):
    return c.width >= 30 and c.height >= 20


def save_clip(page, dpi, rect, out):
    """Render `rect` clamped to the page; skip it if nothing is left."""
    clip = pymupdf.Rect(rect) & page.rect
    if clip.is_empty or clip.width < 1 or clip.height < 1:
        print(f"skipped empty clip {out.name}: {rect}")
        return
    page.get_pixmap(dpi=dpi, clip=clip).save(out)


def render_figures(doc, jobs):
    """Render figure crops from a copy of each page with the prose removed,
    so a neighbouring Problem's words don't bleed into the padding."""
    by_page = {}
    for pno, rect, out in jobs:
        by_page.setdefault(pno, []).append((rect, out))
    for pno, items in by_page.items():
        page = doc[pno]
        for s in spans_of(page):
            if s["line_len"] > 10 or s["bbox"][0] < 160:
                page.add_redact_annot(pymupdf.Rect(s["bbox"]))
        page.apply_redactions(
            images=pymupdf.PDF_REDACT_IMAGE_NONE,
            graphics=pymupdf.PDF_REDACT_LINE_ART_NONE,
        )
        for rect, out in items:
            save_clip(page, FIG_DPI, rect, out)


def unreadable_anchors(page):
    """Tops of gutter anchors whose number glyphs have no Unicode mapping
    (2016 National: "8." reads back as "\\x1b\\x11", "18." as "1\\x1b\\x11"):
    a left-gutter line that isn't a readable "N." but goes on to a blank."""
    tops = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            spans = [s for s in line["spans"] if s["text"].strip()]
            if not spans:
                continue
            first, text = spans[0], "".join(s["text"] for s in line["spans"])
            if (first["bbox"][0] < 60 and first["size"] >= 11
                    and not ANCHOR.match(first["text"])
                    and re.match(r"^\S{1,4}\s+_{3,}", text.strip())):
                tops.append(first["bbox"][1])
    return tops


def extract_round(doc, rnd, work):
    problems, fig_jobs, last_num = [], [], 0
    for pno, page in enumerate(doc):
        spans = dedupe(spans_of(page))
        anchors = []
        for s in spans:
            m = ANCHOR.match(s["text"])
            if m and s["bbox"][0] < 60 and s["size"] >= 11:
                anchors.append((int(m.group(1)), s["bbox"][1]))
        anchors += [(None, y) for y in unreadable_anchors(page)
                    if all(abs(y - a[1]) > 2 for a in anchors)]
        if not anchors:
            continue
        anchors.sort(key=lambda a: a[1])
        # an unreadable anchor takes the number after the one before it
        for i, (num, y) in enumerate(anchors):
            if num is None:
                prev = anchors[i - 1][0] if i else last_num
                anchors[i] = (prev + 1, y)
                print(f"{rnd}: unreadable anchor numbered {prev + 1} by sequence (page {pno + 1})")
        last_num = anchors[-1][0]
        footer = min(
            (s["bbox"][1] for s in spans if s["text"].startswith("Copyright")),
            default=page.rect.height - 40,
        )
        clusters = drawing_clusters(page)
        for i, (num, top) in enumerate(anchors):
            bottom = anchors[i + 1][1] - 4 if i + 1 < len(anchors) else footer - 4
            band = pymupdf.Rect(36, top - 4, page.rect.width - 36, bottom)
            figs = [
                c for c in clusters
                if band.y0 <= (c.y0 + c.y1) / 2 <= band.y1 and c.x0 > 150 and is_figure(c)
            ]
            inline = [
                c for c in clusters
                if band.y0 <= (c.y0 + c.y1) / 2 <= band.y1 and c.x0 > 150 and not is_figure(c)
            ]
            grown = pymupdf.Rect(band)
            for c in figs:
                grown |= c
            in_band = [s for s in spans if band.y0 <= (s["bbox"][1] + s["bbox"][3]) / 2 <= band.y1]
            unit_spans = [
                s for s in in_band
                if 68 <= s["bbox"][0] < 160 and 5 < s["size"] <= 10.5 and not ANCHOR.match(s["text"])
            ]
            unit = span_text(unit_spans).replace("-\n", "").replace("\n", " ") or None
            text_spans = [s for s in in_band if s["bbox"][0] >= 160]
            name = f"{rnd}-{num:02d}"
            save_clip(page, CROP_DPI, grown + (-2, -6, 2, 6), work / "crops" / f"{name}.png")
            fig_rect = None
            if figs:
                fig_rect = pymupdf.Rect(figs[0])
                for c in figs[1:]:
                    fig_rect |= c
                # pull in short label words that sit on or next to the drawing
                pad = fig_rect + (-14, -14, 14, 14)
                for s in spans:
                    if (pad.intersects(pymupdf.Rect(s["bbox"])) and s["bbox"][0] >= 160
                            and s["line_len"] <= 10):
                        fig_rect |= pymupdf.Rect(s["bbox"])
                fig_rect = fig_rect + (-6, -6, 6, 6)
                fig_jobs.append((pno, fig_rect, work / "figcrops" / f"{name}.png"))
            problems.append({
                "round": rnd,
                "problemNumber": num,
                "page": pno + 1,
                "textLayer": span_text(text_spans),
                "unit": unit,
                "figure": [round(v, 1) for v in fig_rect] if fig_rect else None,
                "inlineVectors": len(inline),
            })
    render_figures(doc, fig_jobs)
    return problems


ANSWER_ANCHOR = re.compile(r"(\d+)\.[\s_]*")


def answer_anchor(s):
    """Answer number of an anchor span: "12.", "12.\t", or "12. ______"
    (the 2012–2013 keys put the blank in the anchor span)."""
    m = ANSWER_ANCHOR.fullmatch(s["text"].strip())
    return int(m.group(1)) if m else None


def stacks(page, spans):
    """Group the numerator and denominator of each stacked fraction: the
    spans centred within 12 points of a short horizontal rule (the fraction
    bar) that they overlap. Every other span is a group of its own."""
    bars = [
        d["rect"] for d in page.get_drawings()
        if d["rect"].height < 1 and 3 < d["rect"].width < 60
    ]
    groups, used = [], set()
    for bar in bars:
        g = [
            s for s in spans
            if id(s) not in used
            and min(s["bbox"][2], bar.x1) - max(s["bbox"][0], bar.x0) > 1
            and abs((s["bbox"][1] + s["bbox"][3]) / 2 - bar.y0) < 12
        ]
        if len(g) >= 2:
            used.update(id(s) for s in g)
            groups.append(g)
    return groups + [[s] for s in spans if id(s) not in used]


def extract_answers(doc, work):
    """Raw answer-key reading: each anchor belongs to the nearest Round
    heading above it (one page can hold several Rounds), value right of N."""
    answers, rnd = {}, None
    for pno, page in enumerate(doc):
        page.get_pixmap(dpi=120).save(work / "pages" / f"answers-p{pno + 1}.png")
        spans = dedupe(join_split_anchors(spans_of(page)))
        headings = []
        for s in spans:
            m = re.match(r"(Sprint|Target|Team|Countdown) Round", s["text"].strip())
            if m and s["size"] >= 12:
                headings.append((s["bbox"][1], m.group(1).lower()))
        headings.sort()
        anchors = [s for s in spans if answer_anchor(s) is not None]
        # value window right of each anchor; it ends where the next column's
        # anchor on the same row starts, or at Problem prose (2021 National's
        # key is the Test booklet with the answers written in the blanks)
        prose = [s for s in spans if s["line_len"] > 40]
        windows = []
        for a in anchors:
            x0, y0, _, y1 = a["bbox"]
            x_end = min([x0 + 190] + [
                b["bbox"][0] for b in anchors
                if b["bbox"][0] > x0 + 20 and abs(b["bbox"][1] - y0) < 8
            ] + [
                s["bbox"][0] for s in prose
                if s["bbox"][0] > x0 + 20 and y0 - 16 < s["bbox"][1] < y1 + 4
            ])
            windows.append((x0, x_end, y0 - 16, y1 + 4, (y0 + y1) / 2))
        # a value can fall in two windows; it belongs to the anchor whose row
        # it is nearest. A stacked fraction's numerator sits nearer the row
        # above, so its pieces are grouped and placed by the group's centre.
        values = {id(a): [] for a in anchors}
        for group in stacks(page, [s for s in spans if answer_anchor(s) is None]):
            box = pymupdf.Rect(group[0]["bbox"])
            for s in group[1:]:
                box |= pymupdf.Rect(s["bbox"])
            mid = (box.y0 + box.y1) / 2
            owners = [
                (abs(mid - cy), i) for i, (x0, x1, top, bot, cy) in enumerate(windows)
                if x0 < box.x0 < x1 and (top < box.y0 < bot or top < mid < bot)
            ]
            if owners:
                values[id(anchors[min(owners)[1]])] += group
        for a in anchors:
            above = [h for y, h in headings if y <= a["bbox"][1] + 2]
            a_rnd = above[-1] if above else rnd
            if a_rnd is None:
                continue
            num = answer_anchor(a)
            right = sorted(values[id(a)], key=lambda s: (s["bbox"][1], s["bbox"][0]))
            raw = " ".join(s["text"].strip() for s in right).replace("_", "").strip()
            answers.setdefault(a_rnd, {}).setdefault(str(num), re.sub(r"\s+", " ", raw))
        if headings:
            rnd = headings[-1][1]
    return answers


SOLUTION_COUNTS = {"sprint": 30, "target": 8, "team": 10}


def extract_solutions(doc, work):
    imgs = work / "solution-images"
    lines = []
    for pno, page in enumerate(doc):
        page.get_pixmap(dpi=110).save(work / "pages" / f"solutions-p{pno + 1}.png")
        for i, img in enumerate(page.get_images(full=True)):
            pix = pymupdf.Pixmap(doc, img[0])
            if pix.n - pix.alpha >= 4:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            pix.save(imgs / f"p{pno + 1}-{i + 1}.png")
        lines += page.get_text().splitlines()
    heading = re.compile(r"^(Sprint|Target|Team)[\s ]+(\d+)\s*$")
    if any(heading.match(line.strip()) for line in lines):
        return split_solutions(lines, heading)
    return split_numbered_solutions(lines)


def split_solutions(lines, heading):
    """2021+ layout: a "Sprint 12" heading line before each solution."""
    sols, cur, buf = {}, None, []
    for line in lines:
        m = heading.match(line.strip())
        if m:
            if cur:
                sols[cur] = "\n".join(buf).strip()
            cur, buf = f"{m.group(1).lower()}-{int(m.group(2)):02d}", []
        elif cur:
            buf.append(line)
    if cur:
        sols[cur] = "\n".join(buf).strip()
    return sols


def split_numbered_solutions(lines):
    """Pre-2021 layout: "N. ..." items under a "Sprint Round" heading (or a
    "Sprint Round Solutions" title), or with no Round headings at all.

    A line starts a solution only when its number is the next one expected,
    so stray "64.  Ans." or "1.944 − 0.027" lines inside a solution are
    kept as text. A Round heading, or numbering that restarts at 1 once a
    Round is complete, moves on to the next Round."""
    item = re.compile(r"^[\s\u2007]*(\d+)\.(?:\s+(.*))?$")
    section = re.compile(r"^(?:.{0,50}\s)?(Sprint|Target|Team) Round(?: Solutions)?\s*$")
    order = list(SOLUTION_COUNTS)
    sols, rnd, num, buf = {}, None, 0, []

    def flush():
        if rnd and num:
            sols[f"{rnd}-{num:02d}"] = "\n".join(buf).strip()

    for line in lines:
        m = section.match(line.strip())
        if m and m.group(1).lower() == rnd:
            continue  # repeated page title
        if m and (
                rnd is None or order.index(m.group(1).lower()) > order.index(rnd)):
            flush()
            rnd, num, buf = m.group(1).lower(), 0, []
            continue
        m = item.match(line)
        if m:
            n = int(m.group(1))
            if rnd is None and n == 1:
                rnd = order[0]
            restart = (n == 1 and rnd and num == SOLUTION_COUNTS[rnd]
                       and order.index(rnd) + 1 < len(order))
            if rnd and (n == num + 1 or restart):
                flush()
                if restart:
                    rnd = order[order.index(rnd) + 1]
                num, buf = n, [m.group(2) or ""]
                continue
        if rnd and num:
            buf.append(line)
    flush()
    return sols


def render_solution_figures(doc, work):
    """Solution figures are vector drawings with tiny raster label glyphs, and
    Word's layout makes them hard to cluster, so their page and rectangle (in
    PDF points) are listed by hand in review.json under "solutionFigures"."""
    review = work / "review.json"
    if not review.exists():
        return 0
    figs = json.loads(review.read_text()).get("solutionFigures", {})
    for key, (page, x0, y0, x1, y1) in figs.items():
        save_clip(doc[page - 1], FIG_DPI, pymupdf.Rect(x0, y0, x1, y1),
                  work / "figcrops" / f"solution-{key}.png")
    return len(figs)


def main(src, work):
    src, work = Path(src), Path(work)
    for sub in ["crops", "figcrops", "pages", "solution-images"]:
        (work / sub).mkdir(parents=True, exist_ok=True)
    draft = {"problems": [], "answers": {}, "solutions": {}}
    for rnd in ROUNDS:
        pdf = src / f"{rnd}.pdf"
        if pdf.exists():
            draft["problems"] += extract_round(pymupdf.open(pdf), rnd, work)
    if (src / "answers.pdf").exists():
        draft["answers"] = extract_answers(pymupdf.open(src / "answers.pdf"), work)
    if (src / "solutions.pdf").exists():
        sol_doc = pymupdf.open(src / "solutions.pdf")
        draft["solutions"] = extract_solutions(sol_doc, work)
        print("solution figures", render_solution_figures(sol_doc, work))
    (work / "draft.json").write_text(json.dumps(draft, indent=2, ensure_ascii=False))
    counts = {r: sum(p["round"] == r for p in draft["problems"]) for r in ROUNDS}
    print("problems", counts)
    print("answers", {r: len(v) for r, v in draft["answers"].items()})
    print("solutions", len(draft["solutions"]))
    print("figures", sum(1 for p in draft["problems"] if p["figure"]))


if __name__ == "__main__":
    main(*sys.argv[1:3])
