"""Archive every MATHCOUNTS problem PDF linked from mathteamnyc.weebly.com.

Usage (standard library only):

    python3 -I scripts/mathcounts/crawl_sources.py --dry-run
    python3 -I scripts/mathcounts/crawl_sources.py \
        --out crawled_data/mathcounts/_sources --delay 1.5

The page lists one heading per year and one line per level (SCHOOL, CHAPTER,
STATE, NATIONAL, PRACTICE, ...), each with Google Drive links named by
material. Problem materials are saved as

    <out>/<year>-<level>[-<n>]/<material>.pdf

for example 2025-chapter/countdown.pdf, and <out>/manifest.json records the
URL, Drive id, size, sha256 and fetch time of each file. Non-problem materials
(Handbook, Results, Competitors, ...) are skipped.

A rerun skips files that already exist, so an interrupted crawl resumes.
Dead links are logged and summarised instead of failing the run. The output
is MATHCOUNTS content: personal use only, never commit it (the repo is public).
"""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

PAGE_URL = "https://mathteamnyc.weebly.com/mathcounts.html"
DOWNLOAD_URL = "https://drive.google.com/uc?export=download&id={id}"
REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "crawled_data" / "mathcounts" / "_sources"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

# Link label (lowercased, whitespace collapsed) -> material file stem.
PROBLEM_MATERIALS = {
    "sprint": "sprint",
    "target": "target",
    "team": "team",
    "cdr": "countdown",
    "countdown": "countdown",
    "masters": "masters",
    "answers": "answers",
    "solutions": "solutions",
    "warmups": "warmups",
    "workouts": "workouts",
    "warmup answers": "warmup-answers",
    "workout answers": "workout-answers",
}
SKIPPED_MATERIALS = {
    "handbook", "results", "competitors", "highlights", "playbook", "postmortem",
}
# A numbered practice set, e.g. "#1 (Oct" -> its own Test <year>-practice-1.
NUMBERED_SET = re.compile(r"^#\s*(\d+)\b")
# What a full competition Test usually holds; used only to report gaps.
EXPECTED_ROUNDS = ["sprint", "target", "team", "countdown", "answers", "solutions"]
STANDARD_LEVELS = ["school", "chapter", "state", "national"]

DRIVE_ID_PATTERNS = [
    re.compile(r"/(?:file|document|spreadsheets|presentation)/(?:u/\d+/)?d/([A-Za-z0-9_-]{10,})"),
    re.compile(r"[?&]id=([A-Za-z0-9_-]{10,})"),
    re.compile(r"/folders/([A-Za-z0-9_-]{10,})"),
]


def drive_id(url: str) -> str | None:
    """Return the Drive file id from any Google Drive URL form, else None."""
    host = urllib.parse.urlparse(url).netloc.lower()
    if not (host.endswith("drive.google.com") or host.endswith("docs.google.com")
            or host.endswith("drive.usercontent.google.com")):
        return None
    for pattern in DRIVE_ID_PATTERNS:
        m = pattern.search(url)
        if m:
            return m.group(1)
    return None


def download_url(file_id: str, resource_key: str | None = None) -> str:
    """Direct-download URL; legacy (0B...) ids may also need the resourcekey."""
    url = DOWNLOAD_URL.format(id=file_id)
    return url + (f"&resourcekey={urllib.parse.quote(resource_key)}" if resource_key else "")


def resource_key(url: str) -> str | None:
    values = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("resourcekey")
    return values[0] if values else None


def clean(text: str) -> str:
    text = text.replace(" ", " ").replace("​", "").replace("﻿", "")
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------
# Page parsing


class LineParser(HTMLParser):
    """Flatten the page into lines of text and links (split at <br>/<div>)."""

    BREAKS = {"br", "div", "p", "li", "tr", "td", "h1", "h2", "h3"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[list[tuple]] = [[]]
        self.href: str | None = None
        self.link_text = ""
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.skip += 1
        elif tag == "a":
            self.href = dict(attrs).get("href") or ""
            self.link_text = ""
        elif tag in self.BREAKS:
            self.lines.append([])

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        elif tag == "a" and self.href is not None:
            self.lines[-1].append(("link", clean(self.link_text), self.href))
            self.href = None
        elif tag in self.BREAKS:
            self.lines.append([])

    def handle_data(self, data):
        if self.skip:
            return
        if self.href is not None:
            self.link_text += data
        else:
            self.lines[-1].append(("text", data))


YEAR_LINE = re.compile(r"^((?:19|20)\d\d)$")
LEVEL_LABEL = re.compile(r"^([A-Z][A-Z ]+):")


def parse_page(html: str) -> dict:
    """Parse the page into a plan: problem entries plus everything skipped."""
    parser = LineParser()
    parser.feed(html)
    parser.close()

    entries: list[dict] = []
    skipped: list[dict] = []    # non-problem materials
    unknown: list[dict] = []    # Drive links with a label we don't recognise
    non_drive: list[dict] = []  # links inside a level line that aren't Drive
    levels_seen: dict[int, list[str]] = defaultdict(list)
    drive_links = 0

    year: int | None = None
    level: str | None = None
    for line in parser.lines:
        text = clean("".join(t[1] for t in line if t[0] == "text"))
        links = [t for t in line if t[0] == "link"]
        if not links:
            m = YEAR_LINE.match(text)
            if m:
                year, level = int(m.group(1)), None
            continue
        m = LEVEL_LABEL.match(text)
        if m and year is not None:
            level = m.group(1).strip().lower()
            levels_seen[year].append(level)
        else:
            # Every level line starts with its label; links on any other line
            # (nav menus, resources, footer) are outside the listing.
            level = None
            continue

        seen_in_test: dict[int, set] = defaultdict(set)
        set_no = 1  # bumps when a material repeats on one line (a second set)
        for _, label, href in links:
            did = drive_id(href)
            base = {"year": year, "level": level, "label": label, "url": href}
            if did is None:
                non_drive.append(base)
                continue
            drive_links += 1
            key = label.lower()
            numbered = NUMBERED_SET.match(label)
            if numbered:
                n, material = int(numbered.group(1)), "problems"
            elif key in PROBLEM_MATERIALS:
                material = PROBLEM_MATERIALS[key]
                if material in seen_in_test[set_no]:
                    set_no += 1
                n = set_no
            elif key in SKIPPED_MATERIALS:
                skipped.append({**base, "drive_id": did})
                continue
            else:
                unknown.append({**base, "drive_id": did})
                continue
            seen_in_test[n].add(material)
            entries.append({**base, "drive_id": did, "resource_key": resource_key(href),
                            "set": n, "material": material})

    # Name Tests: "<year>-<level>", with "-<n>" only where a level has several.
    sets_per_level: dict[tuple, set] = defaultdict(set)
    for e in entries:
        sets_per_level[(e["year"], e["level"])].add(e["set"])
    for e in entries:
        multi = len(sets_per_level[(e["year"], e["level"])]) > 1
        e["test"] = f"{e['year']}-{e['level']}" + (f"-{e['set']}" if multi else "")
        e["path"] = f"{e['test']}/{e['material']}.pdf"
        del e["set"]

    return {
        "entries": entries,
        "skipped": skipped,
        "unknown": unknown,
        "non_drive": non_drive,
        "levels_seen": dict(levels_seen),
        "drive_links": drive_links,
    }


def find_gaps(plan: dict) -> list[str]:
    """Human-readable list of missing levels and Rounds, for the summary."""
    by_test: dict[str, set] = defaultdict(set)
    level_of: dict[str, tuple] = {}
    for e in plan["entries"]:
        by_test[e["test"]].add(e["material"])
        level_of[e["test"]] = (e["year"], e["level"])
    gaps = []
    for year, levels in sorted(plan["levels_seen"].items(), reverse=True):
        with_problems = {lvl for (y, lvl) in level_of.values() if y == year}
        for lvl in levels:
            if lvl not in with_problems:
                labels = [x["label"] for x in plan["skipped"] + plan["non_drive"] + plan["unknown"]
                          if x["year"] == year and x["level"] == lvl]
                gaps.append(f"{year}-{lvl}: no problem materials (page lists: {', '.join(labels) or 'nothing'})")
        for lvl in STANDARD_LEVELS:
            if lvl not in levels:
                gaps.append(f"{year}-{lvl}: level not listed")
    for test in sorted(by_test, key=lambda t: (-int(t[:4]), t)):
        mats = by_test[test]
        if "problems" in mats or "warmups" in mats or "workouts" in mats:
            continue  # practice sets have their own shape
        missing = [m for m in EXPECTED_ROUNDS if m not in mats]
        if missing:
            gaps.append(f"{test}: no {', '.join(missing)}")
    return gaps


# --------------------------------------------------------------------------
# Downloading


class RateLimited(Exception):
    pass


class DeadLink(Exception):
    pass


class FormParser(HTMLParser):
    """Collect forms (action + hidden inputs) and hrefs from a Drive page."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[dict] = []
        self.hrefs: list[str] = []
        self._form: dict | None = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "form":
            self._form = {"action": a.get("action") or "", "fields": {}}
            self.forms.append(self._form)
        elif tag == "input" and self._form is not None and a.get("name"):
            self._form["fields"][a["name"]] = a.get("value") or ""
        elif tag == "a" and a.get("href"):
            self.hrefs.append(a["href"])

    def handle_endtag(self, tag):
        if tag == "form":
            self._form = None


def confirm_url(html: str, base: str) -> str | None:
    """Find the "download anyway" target on Drive's virus-scan warning page."""
    p = FormParser()
    p.feed(html)
    for form in p.forms:
        if "confirm" in form["fields"] or "download" in form["action"]:
            action = urllib.parse.urljoin(base, form["action"])
            return action + ("&" if "?" in action else "?") + urllib.parse.urlencode(form["fields"])
    for href in p.hrefs:
        if "confirm=" in href:
            return urllib.parse.urljoin(base, href)
    m = re.search(r'"(https://[^"]*?confirm=[^"]+)"', html)
    if m:
        return m.group(1).replace("\\u003d", "=").replace("\\u0026", "&").replace("&amp;", "&")
    return None


def classify_html(html: str) -> str:
    low = html.lower()
    if "too many users have viewed or downloaded" in low or "quota" in low and "exceeded" in low:
        return "quota"
    if "unusual traffic" in low or "/sorry/" in low:
        return "quota"
    if ("virus scan" in low or "can't scan this file" in low or "download anyway" in low
            or "confirm=" in low):
        return "confirm"
    if "accounts.google.com" in low and ("sign in" in low or "servicelogin" in low):
        return "private"
    if "not found" in low or "does not exist" in low or "error 404" in low:
        return "missing"
    return "unknown"


class Downloader:
    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(self, url: str) -> tuple[bytes, str]:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with self.opener.open(req, timeout=self.timeout) as resp:
                return resp.read(), resp.geturl()
        except urllib.error.HTTPError as err:
            if err.code == 429:
                raise RateLimited(f"HTTP 429 from {url}") from err
            if err.code in (403, 404, 410):
                body = err.read()[:20000].decode("utf-8", "replace")
                if classify_html(body) == "quota":
                    raise RateLimited(f"HTTP {err.code} quota page") from err
                raise DeadLink(f"HTTP {err.code}") from err
            raise

    def fetch_pdf(self, file_id: str, key: str | None = None) -> bytes:
        url = download_url(file_id, key)
        for _ in range(3):  # initial request plus up to two confirm hops
            body, final = self.get(url)
            if body.startswith(b"%PDF"):
                return body
            head = body[:200000].decode("utf-8", "replace")
            if not head.lstrip().startswith("<"):
                raise DeadLink(f"not a PDF (starts with {body[:8]!r})")
            kind = classify_html(head)
            if kind == "quota":
                raise RateLimited("Drive quota / unusual-traffic page")
            if kind == "private":
                raise DeadLink("Drive asks for sign-in (not shared publicly, or needs a resourcekey"
                               " the page doesn't give)")
            if kind == "confirm":
                nxt = confirm_url(head, final)
                if nxt and nxt != url:
                    url = nxt
                    continue
            raise DeadLink(f"Drive returned an HTML page ({kind})")
        raise DeadLink("still HTML after following the confirm form")


# --------------------------------------------------------------------------
# Manifest and summary


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(path: Path) -> dict:
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            print(f"warning: ignoring unreadable {path}", file=sys.stderr)
    return {}


def write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    os.replace(tmp, path)


def print_plan(plan: dict) -> None:
    for e in plan["entries"]:
        print(f"{e['path']:<36} {e['drive_id']:<36} {e['label']}")
    print()
    print(f"Drive links on page:     {plan['drive_links']}")
    print(f"  problem materials:     {len(plan['entries'])}")
    print(f"  skipped (non-problem): {len(plan['skipped'])}")
    print(f"  unrecognised labels:   {len(plan['unknown'])}")
    for u in plan["unknown"]:
        print(f"    {u['year']}-{u['level']}: {u['label']!r} {u['url']}")
    print(f"Non-Drive links in listing: {len(plan['non_drive'])}")
    for u in plan["non_drive"]:
        print(f"    {u['year']}-{u['level']}: {u['label']!r} {u['url']}")
    dup = defaultdict(list)
    for e in plan["entries"]:
        dup[e["drive_id"]].append(e["path"])
    for did, paths in dup.items():
        if len(paths) > 1:
            print(f"  note: Drive id {did} is linked from {', '.join(paths)}")


def print_summary(plan: dict, files: dict, failed: list[dict], out: Path) -> None:
    per_year: dict[int, dict[str, int]] = defaultdict(dict)
    total_bytes = 0
    for e in plan["entries"]:
        rec = files.get(e["path"])
        if rec:
            per_year[e["year"]][e["test"]] = per_year[e["year"]].get(e["test"], 0) + 1
            total_bytes += rec["size"]
    print("\nFiles per Test:")
    for year in sorted(per_year, reverse=True):
        tests = per_year[year]
        cells = ", ".join(f"{t[5:]} {n}" for t, n in sorted(tests.items()))
        print(f"  {year}: {cells}  (total {sum(tests.values())})")
    have = sum(1 for e in plan["entries"] if e["path"] in files)
    print(f"\nTotal: {have}/{len(plan['entries'])} files, {total_bytes / 1e6:.1f} MB in {out}")
    print("\nMissing on the page:")
    for g in find_gaps(plan):
        print(f"  {g}")
    print(f"\nFailed downloads: {len(failed)}")
    for f in failed:
        print(f"  {f['path']}: {f['error']}  ({f['url']})")


# --------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT,
                    help=f"archive folder (default: {DEFAULT_OUT.relative_to(REPO_ROOT)})")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, download nothing")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests (default 1.5)")
    ap.add_argument("--page", type=Path, help="read the page from a saved HTML file instead of the web")
    ap.add_argument("--limit", type=int, help="download at most N new files (for testing)")
    ap.add_argument("--retries", type=int, default=3, help="back-off retries when rate-limited (default 3)")
    ap.add_argument("--backoff", type=float, default=60, help="first back-off wait in seconds (doubles)")
    ap.add_argument("--timeout", type=float, default=60, help="per-request timeout in seconds")
    args = ap.parse_args()

    if args.page:
        html = args.page.read_text(encoding="utf-8")
    else:
        req = urllib.request.Request(PAGE_URL, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=args.timeout) as resp:
            html = resp.read().decode("utf-8", "replace")
    plan = parse_page(html)

    if args.dry_run:
        print_plan(plan)
        print("\nMissing on the page:")
        for g in find_gaps(plan):
            print(f"  {g}")
        return 0

    out: Path = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "manifest.json"
    old = load_manifest(manifest_path)
    files: dict[str, dict] = {f["path"]: f for f in old.get("files", [])}
    failed: list[dict] = []
    dl = Downloader(args.timeout)
    new = 0

    def save_manifest() -> None:
        order = {e["path"]: i for i, e in enumerate(plan["entries"])}
        write_json(manifest_path, {
            "source": PAGE_URL,
            "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "files": sorted(files.values(), key=lambda f: order.get(f["path"], 1 << 30)),
            "failed": failed,
            "skipped": plan["skipped"],
            "unrecognised": plan["unknown"],
            "non_drive": plan["non_drive"],
        })

    for i, e in enumerate(plan["entries"], 1):
        dest = out / e["path"]
        rec_base = {k: e[k] for k in ("path", "test", "year", "level", "material", "label", "drive_id", "url")}
        rec_base["download_url"] = download_url(e["drive_id"], e["resource_key"])
        if dest.exists():
            prev = files.get(e["path"])
            if not prev or prev.get("size") != dest.stat().st_size or prev.get("drive_id") != e["drive_id"]:
                data = dest.read_bytes()  # present from an earlier run or by hand
                files[e["path"]] = {**rec_base, "size": len(data), "sha256": sha256(data),
                                    "fetched_at": (prev or {}).get("fetched_at") or datetime.fromtimestamp(
                                        dest.stat().st_mtime, timezone.utc).isoformat(timespec="seconds")}
            continue
        if args.limit is not None and new >= args.limit:
            break

        wait = args.backoff
        for attempt in range(args.retries + 1):
            time.sleep(args.delay)
            try:
                data = dl.fetch_pdf(e["drive_id"], e["resource_key"])
            except RateLimited as err:
                if attempt == args.retries:
                    failed.append({**rec_base, "error": f"rate-limited: {err}"})
                    print(f"[{i}/{len(plan['entries'])}] {e['path']}: GAVE UP ({err})", flush=True)
                    save_manifest()
                    print("Still rate-limited after retries; stopping. Rerun later to resume.")
                    print_summary(plan, files, failed, out)
                    return 2
                print(f"  rate-limited ({err}); waiting {wait:.0f}s", flush=True)
                time.sleep(wait)
                wait *= 2
                continue
            except (DeadLink, urllib.error.URLError, TimeoutError, OSError) as err:
                failed.append({**rec_base, "error": str(err)})
                print(f"[{i}/{len(plan['entries'])}] {e['path']}: FAILED ({err})", flush=True)
                break
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_suffix(".pdf.part")
            part.write_bytes(data)
            os.replace(part, dest)
            files[e["path"]] = {**rec_base, "size": len(data), "sha256": sha256(data),
                                "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
            new += 1
            print(f"[{i}/{len(plan['entries'])}] {e['path']}: {len(data):,} bytes", flush=True)
            break
        save_manifest()

    save_manifest()
    print_summary(plan, files, failed, out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
