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
            page.get_pixmap(dpi=FIG_DPI, clip=rect).save(out)


def extract_round(doc, rnd, work):
    problems, fig_jobs = [], []
    for pno, page in enumerate(doc):
        spans = dedupe(spans_of(page))
        anchors = []
        for s in spans:
            m = ANCHOR.match(s["text"])
            if m and s["bbox"][0] < 60 and s["size"] >= 11:
                anchors.append((int(m.group(1)), s["bbox"][1]))
        if not anchors:
            continue
        anchors.sort(key=lambda a: a[1])
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
            page.get_pixmap(dpi=CROP_DPI, clip=grown + (-2, -6, 2, 6)).save(work / "crops" / f"{name}.png")
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


def extract_answers(doc, work):
    """Raw answer-key reading: Round from the page header, value right of N."""
    answers, rnd = {}, None
    for pno, page in enumerate(doc):
        page.get_pixmap(dpi=120).save(work / "pages" / f"answers-p{pno + 1}.png")
        spans = dedupe(spans_of(page))
        for s in spans:
            m = re.match(r"(Sprint|Target|Team|Countdown) Round", s["text"].strip())
            if m and s["size"] >= 12:
                rnd = m.group(1).lower()
        if rnd is None:
            continue
        anchors = [s for s in spans if re.fullmatch(r"\d+\.", s["text"].strip().split("\t")[0])]
        for a in anchors:
            num = int(a["text"].strip().split(".")[0])
            x0, y0, _, y1 = a["bbox"]
            right = sorted(
                (s for s in spans
                 if s is not a and x0 < s["bbox"][0] < x0 + 190
                 and y0 - 16 < s["bbox"][1] < y1 + 4
                 and not re.fullmatch(r"\d+\.", s["text"].strip())),
                key=lambda s: (s["bbox"][1], s["bbox"][0]),
            )
            raw = " ".join(s["text"].strip() for s in right).replace("_", "").strip()
            answers.setdefault(rnd, {}).setdefault(str(num), re.sub(r"\s+", " ", raw))
    return answers


def extract_solutions(doc, work):
    heading = re.compile(r"^(Sprint|Target|Team)[\s ]+(\d+)\s*$")
    sols, cur, buf = {}, None, []
    imgs = work / "solution-images"
    for pno, page in enumerate(doc):
        page.get_pixmap(dpi=110).save(work / "pages" / f"solutions-p{pno + 1}.png")
        for i, img in enumerate(page.get_images(full=True)):
            pix = pymupdf.Pixmap(doc, img[0])
            if pix.n - pix.alpha >= 4:
                pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
            pix.save(imgs / f"p{pno + 1}-{i + 1}.png")
        for line in page.get_text().splitlines():
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


def render_solution_figures(doc, work):
    """Solution figures are vector drawings with tiny raster label glyphs, and
    Word's layout makes them hard to cluster, so their page and rectangle (in
    PDF points) are listed by hand in review.json under "solutionFigures"."""
    review = work / "review.json"
    if not review.exists():
        return 0
    figs = json.loads(review.read_text()).get("solutionFigures", {})
    for key, (page, x0, y0, x1, y1) in figs.items():
        doc[page - 1].get_pixmap(dpi=FIG_DPI, clip=pymupdf.Rect(x0, y0, x1, y1)).save(
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
