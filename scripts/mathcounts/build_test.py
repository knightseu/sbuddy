"""Assemble a MATHCOUNTS Test's test.json from the extraction draft and the
reviewed transcriptions.

Usage:

    python3 -I scripts/mathcounts/build_test.py \
        crawled_data/mathcounts/_work/2025-chapter \
        crawled_data/mathcounts/2025-chapter

The work directory holds draft.json and figcrops/ (from extract.py), plus the
review files written during the vision pass (by hand in the pilot, by
vision.py in the bulk run):

- review.json         metadata, unit overrides, alternatives, figure excludes,
                      skipRounds (Rounds left out, e.g. ["countdown"])
- content-*.json      {"sprint-04": "<problem text, $LaTeX$>"}
- answers-*.json      {"sprint-04": "$\\frac{2}{5}$"}
- alternatives-*.json {"team-03": ["12.00"]}, other answers the key accepts
- sol-*.json          {"sprint-04": "<official solution, $LaTeX$>"}; a solution
                      figure is referenced as [DIAGRAM: figures/solution-<key>.png],
                      the marker the viewer already turns into an <img>

Writes <out>/test.json and <out>/figures/*.png in the format decided in #12.
Every Problem in the draft must have content and an answer; the build fails
loudly otherwise, so nothing half-reviewed reaches the importer.
"""

import glob
import json
import re
import shutil
import sys
from pathlib import Path

ROUND_ORDER = {"sprint": 0, "target": 1, "team": 2, "countdown": 3}
SUPERSCRIPTS = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")


def merged(work, pattern):
    out = {}
    for f in sorted(glob.glob(str(work / pattern))):
        out.update(json.loads(Path(f).read_text()))
    return out


def normalize_unit(raw):
    """Text-layer unit -> display unit: 'cm ^{2}' -> 'cm²', '(combi nations)' -> 'combinations'."""
    if not raw:
        return None
    u = raw.replace("_", "").replace("(", "").replace(")", "")
    u = re.sub(r"\s*\^\{(\d+)\}", lambda m: m.group(1).translate(SUPERSCRIPTS), u)
    u = u.strip()
    u = re.sub(r"(\w)- ?\n?\s*(\w)", r"\1\2", u)  # re-join hyphenated line breaks
    u = re.sub(r"\s+", " ", u)
    u = re.sub(r"^combi nations$", "combinations", u)
    u = re.sub(r"^permu tations$", "permutations", u)
    return u or None


def main(work, out):
    work, out = Path(work), Path(out)
    draft = json.loads((work / "draft.json").read_text())
    review = json.loads((work / "review.json").read_text())
    content = merged(work, "content-*.json")
    answers = merged(work, "answers-*.json")
    solutions = merged(work, "sol-*.json")

    excluded = set(review.get("figureExclude", []))
    skip = set(review.get("skipRounds", []))  # Rounds left out of this import, e.g. countdown
    unit_overrides = review.get("unitOverrides", {})
    # alternatives-*.json come from vision.py; review.json entries win
    alternatives = {**merged(work, "alternatives-*.json"), **review.get("answerAlternatives", {})}

    (out / "figures").mkdir(parents=True, exist_ok=True)
    problems, missing = [], []
    for p in sorted((p for p in draft["problems"] if p["round"] not in skip), key=lambda p: (ROUND_ORDER[p["round"]], p["problemNumber"])):
        key = f"{p['round']}-{p['problemNumber']:02d}"
        if key not in content:
            missing.append(f"{key}: content")
        if key not in answers:
            missing.append(f"{key}: answer")
        unit = unit_overrides[key] if key in unit_overrides else normalize_unit(p["unit"])
        entry = {
            "round": p["round"],
            "problemNumber": p["problemNumber"],
            "content": content.get(key, ""),
            "answer": answers.get(key, ""),
        }
        if unit:
            entry["answerUnit"] = unit
        if key in alternatives:
            entry["answerAlternatives"] = alternatives[key]
        entry["solutions"] = [solutions[key]] if key in solutions else []
        for ref in re.findall(r"\[DIAGRAM:\s*figures/([^\]\s]+)\]", " ".join(entry["solutions"])):
            if not (work / "figcrops" / ref).exists():
                missing.append(f"{key}: solution figure {ref}")
            else:
                shutil.copyfile(work / "figcrops" / ref, out / "figures" / ref)
        crop = work / "figcrops" / f"{key}.png"
        if p["figure"] and key not in excluded and crop.exists():
            shutil.copyfile(crop, out / "figures" / f"{key}.png")
            entry["images"] = [f"figures/{key}.png"]
        else:
            entry["images"] = []
        problems.append(entry)

    if missing:
        sys.exit("not reviewed:\n  " + "\n  ".join(missing))

    test = {"metadata": review["metadata"], "problems": problems}
    (out / "test.json").write_text(json.dumps(test, indent=2, ensure_ascii=False) + "\n")
    by_round = {}
    for e in problems:
        by_round[e["round"]] = by_round.get(e["round"], 0) + 1
    print(f"wrote {out / 'test.json'}: {by_round}, "
          f"{sum(bool(e['solutions']) for e in problems)} solutions, "
          f"{sum(bool(e['images']) for e in problems)} figures")


if __name__ == "__main__":
    main(*sys.argv[1:3])
