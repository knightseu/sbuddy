"""Write a starting review.json for MATHCOUNTS work directories.

Usage:

    python3 -I scripts/mathcounts/init_review.py [--skip-rounds countdown] \
        crawled_data/mathcounts/_work/2016-national [more work dirs ...]

metadata comes from the source manifest (_sources/manifest.json, written by
crawl_sources.py) and the Rounds extract.py found in draft.json, with the
Round formats from #10. An existing review.json is never overwritten, so the
hand-edited fields (figureExclude, unitOverrides, answerAlternatives,
solutionFigures, visionOverrides) are safe.
"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "crawled_data" / "mathcounts" / "_sources" / "manifest.json"
ROUNDS = ["sprint", "target", "team", "countdown"]
MATERIALS = ROUNDS + ["answers", "solutions"]

# Round formats never changed from 2010 to 2025 (#10).
FORMATS = {
    "sprint": {"problem_count": 30, "time_limit_seconds": 2400, "time_limit_scope": "round",
               "calculator": False, "team": False},
    "target": {"problem_count": 8, "time_limit_seconds": 360, "time_limit_scope": "group",
               "group_size": 2, "calculator": True, "team": False},
    "team": {"problem_count": 10, "time_limit_seconds": 1200, "time_limit_scope": "round",
             "calculator": True, "team": True},
    "countdown": {"time_limit_seconds": 45, "time_limit_scope": "problem",
                  "calculator": False, "team": False},
}


def review_for(work, files, skip):
    test = work.name
    year, level = test.split("-", 1)
    draft = json.loads((work / "draft.json").read_text())
    counts = {r: sum(p["round"] == r for p in draft["problems"]) for r in ROUNDS}
    rounds = {}
    for r in ROUNDS:
        if counts[r] and r not in skip:
            rounds[r] = dict(FORMATS[r])
            rounds[r]["problem_count"] = counts[r] if r == "countdown" else FORMATS[r]["problem_count"]
    sources = {f["material"]: f["url"].split("?")[0] for f in files
               if f["test"] == test and f["material"] in MATERIALS}
    variant = level.capitalize()
    review = {
        "metadata": {
            "competition": "mathcounts",
            "year": int(year),
            "variant": variant,
            "name": f"MATHCOUNTS {year} {variant}",
            "sources": {m: sources[m] for m in MATERIALS if m in sources},
            "rounds": rounds,
        },
        "figureExclude": [],
        "unitOverrides": {},
        "answerAlternatives": {},
        "solutionFigures": {},
    }
    if skip & {r for r in ROUNDS if counts[r]}:
        review["skipRounds"] = sorted(skip & {r for r in ROUNDS if counts[r]})
    return review


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("work", nargs="+")
    ap.add_argument("--skip-rounds", default="", help="comma-separated Rounds to leave out, e.g. countdown")
    args = ap.parse_args()
    skip = {r for r in args.skip_rounds.split(",") if r}
    files = json.loads(MANIFEST.read_text())["files"]
    for w in map(Path, args.work):
        out = w / "review.json"
        if out.exists():
            print(f"{w.name}: review.json exists, left alone")
            continue
        review = review_for(w, files, skip)
        out.write_text(json.dumps(review, indent=2, ensure_ascii=False) + "\n")
        print(f"{w.name}: rounds {list(review['metadata']['rounds'])}, "
              f"sources {list(review['metadata']['sources'])}, skip {review.get('skipRounds', [])}")


if __name__ == "__main__":
    main()
