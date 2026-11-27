"""Read a MATHCOUNTS Test's crops and pages with a vision model, gate the
result, and write the review files build_test.py merges.

Usage (stdlib only, nothing to install):

    python3 -I scripts/mathcounts/vision.py crawled_data/mathcounts/_work/2025-chapter \
        [more work dirs ...] [--model SPEC] [--fallback SPEC] [--rounds countdown] \
        [--calibrate [--reference pilot|kimi]] [--out DIR] [--write] [--dry-run] [--sample N]

Each work directory must already hold extract.py's output: crops/, pages/,
draft.json, and normally review.json. Decided in #19, #36, #37 and #38:

- A model spec names the backend and the model: ollama:qwen3.6:27b-q8_0 or
  openrouter:moonshotai/kimi-k3.1-pro (a bare name means openrouter:).
  Each pass is chosen by its flag, then MATHCOUNTS_VISION_MODEL /
  MATHCOUNTS_VISION_FALLBACK (environment or the repo's .env), then the
  default: PRIMARY (local qwen3.6 through Ollama) reads, and FALLBACK (Kimi
  K3.1 Pro through OpenRouter) gets one try at each key that fails a gate.
  --fallback "" turns the fall-through off.
- The read is one call per Problem crop, one per answer-key page, one per
  solution page. Shared code fixes run on every model's read: round labels
  only move forward, item numbers are stripped from solutions, plain values
  in Problem text are taken out of math, and the value before a bare "Ans."
  is bolded when it matches the answer key.
- Gates, all hard:
    1. prose word overlap with the text layer >= 90%, per Problem;
    2. each solution's bold final value equals the answer key;
    3. Problem and answer counts match metadata.rounds;
    4. every Problem has content and an answer, and a solution when the Test
       has Solutions.
  A failed key re-reads only the images it came from; with no source, the
  pages between its nearest sourced neighbours. Anything still failing goes
  to <work>/failures.json and the Test is not written. A person can accept a
  known failure in review.json:
      "visionOverrides": {"sprint-27": ["overlap"]}   ("*" for every key)
  and correct a misread, or fix scanned pages that are out of order:
      "visionCorrections": {"answers": {"team-09": "381,649"}}
      "pageOrder": {"solutions": [1, 2, ..., 15, 17, 16]}
- Every response is cached in _work/_vision-cache/, keyed by model + prompt +
  image bytes, so a re-run never pays twice. Ollama entries key on the
  prefixed spec, OpenRouter entries on the bare model name.
- Caps: $5 per Test and $100 per run, counting OpenRouter (Kimi) spend only.
- --rounds countdown reads only those Rounds' crops plus the answer pages
  (no solution pages), gates only those Rounds, and with --write merges the
  new keys into the existing *-vision.json files. Remove the Rounds from
  review.json's skipRounds first.

Ollama: vision.py does not start the server. Run, in its own terminal,

    OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=16384 OLLAMA_NUM_PARALLEL=3 OLLAMA_KEEP_ALIVE=30m ollama serve

(OLLAMA_URL overrides http://127.0.0.1:11435/v1). Start long runs in their
own session, not from a shell that may be torn down, and interrupt the
python3 process itself; the cache resumes a run cleanly.

Output, per work directory (DIR is --out, default vision):

- DIR/content.json, answers.json, alternatives.json, solutions.json,
  report.json (models, Kimi cost, wall time and calls per pass, gates,
  fall-through keys, spot-check list, warnings); with --rounds,
  report-<rounds>.json and the reading files are merged
- failures.json, when a gate still fails after the fall-through
- with --write (DIR must be vision) and all gates passing: content-vision.json,
  answers-vision.json, sol-vision.json and alternatives-vision.json, the
  files build_test.py merges. Refuses if hand-made review files exist.
- with --calibrate: DIR/calibration.md and calibration.json, comparing the
  reading with the hand-verified pilot files (--reference pilot, the bar
  from #19) or with the imported *-vision.json files (--reference kimi, a
  per-key disagreement check).

OPENROUTER_API_KEY comes from the environment or the repo's .env; it is
needed only when a pass uses OpenRouter.

Runbook: docs/MATHCOUNTS_VISION.md.
"""

import argparse
import base64
import concurrent.futures as cf
import hashlib
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "crawled_data" / "mathcounts" / "_work" / "_vision-cache"
API = "https://openrouter.ai/api/v1"
PRIMARY = "ollama:qwen3.6:27b-q8_0"
FALLBACK = "openrouter:moonshotai/kimi-k3.1-pro"
BACKENDS = ("ollama", "openrouter")
OLLAMA_URL = "http://127.0.0.1:11435/v1"
OLLAMA_SERVE = ("OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=16384 "
                "OLLAMA_NUM_PARALLEL=3 OLLAMA_KEEP_ALIVE=30m ollama serve")
OLLAMA_BODY = {"reasoning_effort": "none", "presence_penalty": 0, "max_tokens": 4096}
OLLAMA_TIMEOUT = 3600
CONCURRENCY = {"ollama": 3, "openrouter": 8}  # ollama: match OLLAMA_NUM_PARALLEL (#39)
TEST_CAP = 5.0
RUN_CAP = 100.0
OVERLAP_MIN = 0.90  # share of the reading's words found in the text layer (guards invented prose)
COVER_MIN = 0.75    # share of the text layer's words in the reading; lower, as the layer mixes in figure labels
ROUNDS = ["sprint", "target", "team", "countdown"]
DEFAULT_COUNTS = {"sprint": 30, "target": 8, "team": 10}
SPOT_CHECK = 5

MATH_RULES = r"""- Write math in LaTeX between single dollar signs: $2 + (2 \times 2)$, $\frac{3}{4}$, $2\sqrt{3}$, $x^2$, $\overline{AB}$, $\triangle ABC$, $\angle ABC$, $\pi$.
- Use math only for expressions, equations, variables and symbols. A lone measurement in prose stays plain text (84 in., 15 cm, 3 hours), and so do names of points, segments and shapes in prose (triangle XYZ, side AB, point C). Inside an expression, units use \text: $4\text{ cm} \times 5\text{ cm} = 20\text{ cm}^2$.
- A dollar amount is written as an escaped \$3.00 outside math.
- Symbols: ★ is $\bigstar$, ♥ is $\heartsuit$, ♣ is $\clubsuit$, ♦ is $\diamondsuit$, ♠ is $\spadesuit$.
- Emphasised words: $\textit{word}$ or $\textbf{word}$. Never use Markdown (no *, **, #, | tables, code fences).
- A table of data: $$\begin{array}{|c|c|} \hline a & b \\ \hline \end{array}$$
- A formula displayed on its own line goes in $$...$$, joined to the surrounding text with a space, not a newline.
- Plain numbers in prose stay plain text ("pick 5", "(21, 15, 12)"); use math for expressions and equations.
- Join the lines of a paragraph with single spaces. Use a newline only between separate paragraphs."""

PROBLEM_PROMPT = f"""This image is one problem from a MATHCOUNTS competition booklet. Transcribe the problem statement exactly.

- Output only the problem text: no preamble, no commentary.
- Leave out the problem number, the answer blank, and any unit printed at the answer blank (such as "(cm²)" or "ways").
- Keep every word of the problem, including instructions such as "Express your answer as a common fraction."
{MATH_RULES}
- In problem text, a number with a unit stays plain text ("84 in.", "15 cm", "60 kazoos"), including in measurements ("AB = 5 cm", "AE = 30 m"), and so do names of points and figures ("triangle XYZ", "rectangle ABCD", "XY"). Use math only for expressions, equations, variables such as $x$, and symbols such as $\\overline{{AB}}$ or $\\triangle ABC$.
- If the figure contains a table of data, transcribe it as an array after the text. Do not describe pictures, graphs or geometric diagrams, and do not list their labels."""

ANSWER_PROMPT = r"""This image is one page of a MATHCOUNTS answer key. List every answer on the page, in reading order, one per line, formatted exactly as:
<round> <number>: <answer>

- <round> is sprint, target, team or countdown: the round named by the heading of the section or column the answer is in ("Sprint Round", "Target Round", "Team Round", "Countdown Round"). If no heading on this page applies to the answer, write ? as the round.
- <answer> is the answer only, without the unit printed at the blank (cm², ways, years, ...). Write math as LaTeX without dollar signs: \frac{2}{5}, 36\pi, 2\sqrt{3}, 3\sqrt[3]{450}. Keep digits, commas, decimals and words exactly as printed (18,050 or 275.35 or Blue).
- If the key accepts more than one answer ("12 or 12.00", "Blue or B"), separate them with " || " in the printed order.
- If the page has no answers (a cover or instruction page), output exactly NONE.
- No other text."""

SOLUTION_PROMPT = f"""This image is one page of official MATHCOUNTS solutions. Transcribe every solution on the page.

Start each solution with a header line of the form
=== <round> <number>
where <round> is sprint, target, team or countdown, from the solution's heading ("Sprint 13") or from the round heading above a numbered item ("13." under "Sprint Round"). If the round heading is not on this page, write ? as the round. If the page begins with text that continues a solution from the previous page, put that text first, under the header line
=== continued

- Transcribe exactly. Do not solve, shorten or correct anything. If the source has a typo, a wrong number or
  a mathematical error, copy it as printed: this is a transcription, not an edit.
{MATH_RULES}
- Put the final answer printed in bold in \\mathbf: $\\mathbf{{14}}$, $\\mathbf{{\\frac{{3}}{{88}}}}$, $\\mathbf{{9}}\\text{{ cm}}^2$.
- Where the solution has a figure or diagram, write [DIAGRAM] at that spot and do not describe it.
- Ignore page headers, footers and copyright lines.
- If the page has no solutions, output exactly NONE."""


class CapExceeded(Exception):
    pass


class OllamaUnavailable(Exception):
    pass


# --------------------------------------------------------------------------
# Model specs, configuration, and a client with an on-disk cache and cost caps


def parse_spec(spec):
    """'ollama:qwen3.6:27b-q8_0' -> ('ollama', 'qwen3.6:27b-q8_0'); a bare
    name means OpenRouter."""
    backend, sep, model = spec.partition(":")
    if sep and backend in BACKENDS:
        return backend, model
    return "openrouter", spec


def full_spec(spec):
    backend, model = parse_spec(spec)
    return f"{backend}:{model}"


def env_value(name):
    """From the environment, else the repo's .env; placeholders count as unset."""
    value = os.environ.get(name)
    env = ROOT / ".env"
    if value is None and env.exists():
        for line in env.read_text().splitlines():
            m = re.match(rf"\s*{re.escape(name)}\s*=\s*(.*?)\s*$", line)
            if m:
                value = m.group(1).strip("'\"")
    return None if value == "placeholder" else value


def load_key():
    return env_value("OPENROUTER_API_KEY") or None


def choose(flag, env_name, default):
    """Flag, then environment / .env, then the code default. '' means off."""
    if flag is not None:
        return flag
    value = env_value(env_name)
    return value if value is not None else default


class Client:
    def __init__(self, key, dry_run=False, ollama_url=None):
        self.key = key
        self.dry_run = dry_run
        self.ollama_url = (ollama_url or OLLAMA_URL).rstrip("/")
        self.lock = threading.Lock()
        self.run_cost = 0.0
        self.test_cost = {}
        self.calls = {}       # backend -> {"cached": n, "api": n, ...}
        self.test_calls = {}  # (test, backend) -> {"cached": n, "api": n, ...}
        self._pricing = None
        self._ollama_ok = set()
        CACHE.mkdir(parents=True, exist_ok=True)

    def count(self, test, backend, what):
        with self.lock:
            for d in (self.calls.setdefault(backend, {}), self.test_calls.setdefault((test, backend), {})):
                d[what] = d.get(what, 0) + 1

    def cache_path(self, spec, prompt, png):
        backend, model = parse_spec(spec)
        # OpenRouter keeps hashing the bare name so the Kimi entries made before #38 still match
        tag = model if backend == "openrouter" else f"{backend}:{model}"
        h = hashlib.sha256()
        for part in (tag.encode(), prompt.encode(), png):
            h.update(hashlib.sha256(part).digest())
        return CACHE / f"{h.hexdigest()}.json"

    def complete(self, test, spec, prompt, image):
        backend, model = parse_spec(spec)
        png = image.read_bytes()
        path = self.cache_path(spec, prompt, png)
        if path.exists():
            self.count(test, backend, "cached")
            return json.loads(path.read_text())["text"]
        if self.dry_run:
            self.count(test, backend, "skipped")
            return None
        if backend == "ollama":
            self.check_ollama(model)
        with self.lock:
            if self.run_cost >= RUN_CAP:
                raise CapExceeded(f"run cap ${RUN_CAP:.2f} reached")
            if self.test_cost.get(test, 0.0) >= TEST_CAP:
                raise CapExceeded(f"{test}: Test cap ${TEST_CAP:.2f} reached")
        for _ in range(3):  # an empty reply (reasoning used up the output) is retried, never cached
            t0 = time.time()
            text, usage, cost = self.request(backend, model, prompt, png)
            usage = dict(usage, wallSeconds=round(time.time() - t0, 1))
            self.count(test, backend, "api")
            with self.lock:
                self.run_cost += cost
                self.test_cost[test] = self.test_cost.get(test, 0.0) + cost
            if text.strip() or usage.get("error"):
                break
        if not text.strip() and not usage.get("error"):
            self.count(test, backend, "empty")
            return ""
        # a repeat-limit reply is deterministic at temperature 0: cached as an empty (failed) read
        path.write_text(json.dumps({
            "backend": backend, "model": model, "image": image.name, "text": text, "usage": usage,
            "cost": cost, "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }, ensure_ascii=False))
        return text

    def check_ollama(self, model):
        """Once per model: the server answers and the model has been pulled."""
        if model in self._ollama_ok:
            return
        with self.lock:
            if model in self._ollama_ok:
                return
            try:
                with urllib.request.urlopen(f"{self.ollama_url}/models", timeout=10) as r:
                    have = {m["id"] for m in json.load(r).get("data", [])}
            except (urllib.error.URLError, TimeoutError, OSError, ValueError) as e:
                raise OllamaUnavailable(
                    f"Ollama is not reachable at {self.ollama_url} ({e}). Start it in its own terminal:\n"
                    f"    {OLLAMA_SERVE}") from e
            if model not in have:
                raise OllamaUnavailable(
                    f"Ollama at {self.ollama_url} has no model {model!r}. Pull it with:\n"
                    f"    OLLAMA_HOST={self.ollama_url.split('//')[-1].removesuffix('/v1')} ollama pull {model}")
            self._ollama_ok.add(model)

    def request(self, backend, model, prompt, png):
        ollama = backend == "ollama"
        body = {
            "model": model,
            "temperature": 0,
            "usage": {"include": True},
            "messages": [{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {
                    "url": "data:image/png;base64," + base64.b64encode(png).decode()}},
            ]}],
        }
        if ollama:
            body.update(OLLAMA_BODY)
        name = "Ollama" if ollama else "OpenRouter"
        req = urllib.request.Request(
            f"{self.ollama_url if ollama else API}/chat/completions", data=json.dumps(body).encode(),
            headers={"Authorization": "Bearer ollama" if ollama else f"Bearer {self.key}",
                     "Content-Type": "application/json"})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=OLLAMA_TIMEOUT if ollama else 300) as r:
                    data = json.load(r)
                if "error" in data:
                    raise RuntimeError(f"{name} error: {data['error']}")
                break
            except urllib.error.HTTPError as e:
                detail = e.read()[:300].decode(errors="replace")
                if ollama and "repeat limit" in detail:  # a deterministic loop: a failed read, not a retry
                    return "", {"error": "repeat-limit"}, 0.0
                if e.code in (408, 429, 500, 502, 503, 504) and attempt < 4:
                    time.sleep(2 ** attempt * 3)
                    continue
                raise RuntimeError(f"{name} HTTP {e.code}: {detail}") from e
            except (urllib.error.URLError, TimeoutError):
                if attempt < 4:
                    time.sleep(2 ** attempt * 3)
                    continue
                raise
        choice = data["choices"][0]
        text = strip_fences(choice["message"].get("content") or "")
        usage = data.get("usage") or {}
        if ollama:
            return text, dict(usage, finish=choice.get("finish_reason")), 0.0
        cost = usage.get("cost")
        if cost is None:
            cost = self.price(model, usage)
        return text, usage, float(cost)

    def price(self, model, usage):
        if self._pricing is None:
            with urllib.request.urlopen(f"{API}/models", timeout=60) as r:
                self._pricing = {m["id"]: m.get("pricing", {}) for m in json.load(r)["data"]}
        p = self._pricing.get(model, {})
        return (usage.get("prompt_tokens", 0) * float(p.get("prompt", 0))
                + usage.get("completion_tokens", 0) * float(p.get("completion", 0)))


def strip_fences(text):
    text = text.strip()
    m = re.fullmatch(r"```[a-zA-Z]*\n(.*?)\n?```", text, re.S)
    return m.group(1).strip() if m else text


# --------------------------------------------------------------------------
# Parsing model output


def key_of(rnd, num):
    return f"{rnd}-{int(num):02d}"


def page_no(path):
    return int(re.search(r"-p(\d+)\.png$", path.name).group(1))


def parse_answer_page(text):
    """'sprint 4: \\frac{2}{5}' lines -> [(round or None, number, [answers])]."""
    out = []
    if not text or text.strip() == "NONE":
        return out
    line_re = re.compile(r"^\s*(sprint|target|team|countdown|\?)\s+(\d+)\s*[:.]\s*(.*?)\s*$", re.I)
    for line in text.splitlines():
        m = line_re.match(line)
        if not m or not m.group(3):
            continue
        rnd = None if m.group(1) == "?" else m.group(1).lower()
        answers = [a.strip().strip("$").strip() for a in m.group(3).split("||")]
        out.append((rnd, int(m.group(2)), [a for a in answers if a]))
    return out


def as_display(answer):
    """LaTeX answers are shown in math; plain ones (18,050, Blue) are not."""
    return f"${answer}$" if re.search(r"[\\^_{}]", answer) else answer


def resolve_round(explicit, rnd, prev_num, num):
    """Round for an item: the explicit one, else the current one, moving to
    the next Round when '?' numbering restarts (Sprint 30, then '? 4').
    Rounds only move forward: an explicit Round earlier than the current one
    ('sprint 4' after 'target 3') is a mislabel and is treated as '?' (#37)."""
    if explicit and rnd in ROUNDS and explicit in ROUNDS and ROUNDS.index(explicit) < ROUNDS.index(rnd):
        explicit = None
    if explicit:
        return explicit
    if rnd in ROUNDS and prev_num is not None and num <= prev_num and rnd != ROUNDS[-1]:
        return ROUNDS[ROUNDS.index(rnd) + 1]
    return rnd


def assemble_answers(page_texts):
    """Answers from pages in page order; '?' continues the last round seen."""
    answers, alternatives, source, warnings = {}, {}, {}, []
    rnd, prev = None, None
    for page, text in page_texts:
        for item_rnd, num, vals in parse_answer_page(text):
            rnd = resolve_round(item_rnd, rnd, prev, num)
            prev = num
            if rnd is None or not vals:
                warnings.append(f"{page}: answer {num} has no round")
                continue
            k = key_of(rnd, num)
            if k in answers:
                warnings.append(f"{page}: duplicate answer {k}")
                continue
            answers[k] = as_display(vals[0])
            if len(vals) > 1:
                alternatives[k] = vals[1:]
            source[k] = page
    return answers, alternatives, source, warnings


def parse_solution_page(text):
    """'=== sprint 13' sections -> [(header, body)]; header is 'continued',
    (round or None, number), or None for text before any header."""
    out = []
    if not text or text.strip() == "NONE":
        return out
    header_re = re.compile(r"^===\s*(?:(continued)|(sprint|target|team|countdown|\?)\s+(\d+))\s*$", re.I)
    cur, buf = None, []
    for line in text.splitlines():
        m = header_re.match(line.strip())
        if m:
            if cur is not None or "".join(buf).strip():
                out.append((cur, "\n".join(buf).strip()))
            if m.group(1):
                cur = "continued"
            else:
                cur = (None if m.group(2) == "?" else m.group(2).lower(), int(m.group(3)))
            buf = []
        else:
            buf.append(line)
    if cur is not None or "".join(buf).strip():
        out.append((cur, "\n".join(buf).strip()))
    return [strip_item_number(h, b) for h, b in out]


ITEM_NUMBER = re.compile(r"^\s*(\d{1,2})\.\s+")


def strip_item_number(header, body):
    """'=== sprint 5' then '5. A pyramid ...': drop the repeated item number.
    A '=== continued' block that starts with an item number is really that
    item's header (#37)."""
    m = ITEM_NUMBER.match(body or "")
    if not m:
        return header, body
    if header == "continued":
        header = (None, int(m.group(1)))
    if isinstance(header, tuple) and header[1] == int(m.group(1)):
        body = body[m.end():]
    return header, body


def assemble_solutions(page_texts, figure_keys):
    solutions, source, warnings = {}, {}, []
    rnd, last, prev = None, None, None
    for page, text in page_texts:
        for header, body in parse_solution_page(text):
            if header in ("continued", None):
                if last and body:
                    solutions[last] = (solutions[last] + " " + body).strip()
                    source.setdefault(last, []).append(page)
                elif body:
                    warnings.append(f"{page}: continued text with no solution before it")
                continue
            h_rnd, num = header
            rnd = resolve_round(h_rnd, rnd, prev, num)
            prev = num
            if rnd is None:
                warnings.append(f"{page}: solution {num} has no round")
                continue
            last = key_of(rnd, num)
            if last in solutions:
                warnings.append(f"{page}: duplicate solution {last}")
            solutions[last] = body
            source[last] = [page]
    for k, text in solutions.items():
        if "[DIAGRAM]" in text:
            if k in figure_keys:
                text = text.replace("[DIAGRAM]", f"[DIAGRAM: figures/solution-{k}.png]", 1)
            else:
                warnings.append(f"{k}: solution has a figure but review.json has no solutionFigures rectangle")
            solutions[k] = re.sub(r"\s*\[DIAGRAM\]\s*", " ", text).strip()
    for k in figure_keys:
        if k in solutions and f"solution-{k}.png" not in solutions[k]:
            solutions[k] = f"[DIAGRAM: figures/solution-{k}.png] " + solutions[k]
    return solutions, source, warnings


SUPERSCRIPT = {"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4", "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"}


def tidy(text):
    """House style the prompt can't reliably enforce: straight quotes, and
    Unicode superscripts as LaTeX (cm² -> cm$^2$, or ^2 when already in math)."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    out, in_math = [], False
    for i, ch in enumerate(text):
        if ch == "$" and (i == 0 or text[i - 1] != "\\"):
            in_math = not in_math
        if ch in SUPERSCRIPT:
            out.append(f"^{SUPERSCRIPT[ch]}" if in_math else f"$^{SUPERSCRIPT[ch]}$")
        else:
            out.append(ch)
    return "".join(out)


# Plain values in Problem text that the house style keeps out of math (#37):
# numbers, point names of 2+ letters (a lone $A$ is usually a variable), measurements,
# units, percents and escaped dollar amounts.
UNIT = r"\\text\{\s*([a-zA-Z.]+)\}(\^\{?(\d)\}?)?"
NUM = r"\d[\d,]*(?:\.\d+)?"
NAME = r"[A-Z]{2,5}"
PLAIN = re.compile(rf"^(?:{NAME}(?:\s*=\s*{NAME})*\s*=\s*)?{NUM}(?:\s*{UNIT}|\\%)?$"  # 5, 5 cm, AB = BC = 5 cm, 25%
                   rf"|^{NAME}(?:\s*\+\s*{NAME})*$"                                  # ABCD, PA + PB
                   rf"|^{NUM}(?:,\s*{NUM})+$"                                         # 1, 2, 3, 4
                   rf"|^{UNIT}$"                                                      # \text{cm}^2
                   rf"|^\\\${NUM}$")                                                 # \$1.49
INLINE_MATH = re.compile(r"(?<![\\$])\$(?!\$)((?:\\\$|[^$])+?)(?<!\\)\$(?!\$)")


def plain(span):
    s = re.sub(UNIT, lambda m: " " + m.group(1) + (f"$^{m.group(3)}$" if m.group(3) else ""), span.strip())
    return re.sub(r"\s+", " ", s.replace("\\%", "%")).strip()


def demath(text):
    """Problem text only: inline spans that are just a plain value become text,
    and a $$...$$ display joins its paragraph with a space."""
    text = INLINE_MATH.sub(lambda m: plain(m.group(1)) if PLAIN.match(m.group(1).strip()) else m.group(0), text)
    text = re.sub(r"\s*\n+\s*(\$\$)", r" \1", text)
    return re.sub(r"(\$\$[^$]+\$\$)\s*\n+\s*", r"\1 ", text)


ANS_END = re.compile(r"\$?\\math(?:bf|rm)\{Ans\.?\}\$?\.?\s*$|\bAns\.?\s*$")


def bold_final(solution, accepted):
    r"""Pre-2021 layout, where only "Ans." is bold: "= 50 $\mathbf{Ans}$" becomes
    "= $\mathbf{50}$ Ans." when 50 is an accepted answer, so every layout ends
    on a bold final value (#37). Anything else is left alone."""
    m = ANS_END.search(solution)
    if not m or [b for b in bold_values(solution) if not b.startswith("Ans")]:
        return solution
    want = {norm_value(a) for a in accepted}
    head = solution[:m.start()].rstrip()
    mm = re.search(r"(=\s*|\s)([^\s=$]+)(\$?)\s*$", head)
    if not mm or norm_value(mm.group(2)) not in want:
        return solution
    val = mm.group(2).rstrip(".")
    in_math = mm.group(3) == "$" or head[:mm.start(2)].count("$") % 2
    bold = f"\\mathbf{{{val}}}" if in_math else f"$\\mathbf{{{val}}}$"
    return head[:mm.start(2)] + bold + head[mm.end(2):] + " Ans."


# --------------------------------------------------------------------------
# Gates


def prose_words(text, displays=True):
    """Prose words of 3+ letters, without LaTeX command and environment names.
    displays=False leaves out $$...$$ blocks (often a table read from a
    figure, which the text layer may lack)."""
    text = text or ""
    if not displays:
        text = re.sub(r"\$\$.*?\$\$", " ", text, flags=re.S)
    text = re.sub(r"\\(?:begin|end)\{[^}]*\}(?:\{[^}]*\})?", " ", text)
    text = re.sub(r"\\[A-Za-z]+", " ", text)
    return set(re.findall(r"[a-z]{3,}", text.lower()))


def overlap(text_layer, vision):
    """-> (covered, faithful): share of text-layer words in the reading
    (display blocks included), and share of the reading's words outside
    display blocks that are in the text layer."""
    a = prose_words(text_layer)
    if not a:
        return 1.0, 1.0
    # the text layer runs words together ("dabcsuch", "evenn"), so a word also
    # matches when it is inside a layer token, or the token is inside it
    def found(w, pool):
        return w in pool or any(len(x) >= 3 and (x in w or w in x) for x in pool)
    seen = prose_words(vision)
    covered = sum(found(w, seen) for w in a) / len(a)
    b = prose_words(vision, displays=False)
    faithful = sum(found(w, a) for w in b) / len(b) if b else 1.0
    return covered, faithful


def norm_value(s):
    s = (s or "").replace("\\$", "").replace("$", "")
    s = re.sub(r"\\(?:mathbf|textbf|boldsymbol|bm)\b", "", s)
    s = re.sub(r"\\text\s*\{[^{}]*\}", "", s)
    s = re.sub(r"\\%|%|\^\s*\{?\\circ\}?|°|\\approx", "", s)  # 25% vs 25, 30° vs 30
    s = re.sub(r"\\[dt]frac", r"\\frac", s)
    s = s.replace("{,}", ",").replace("{:}", ":")
    s = re.sub(r"\s*[ap]\.\s?m\.?\s*$", "", s, flags=re.I)  # 1:30 p.m. vs 1:30
    s = re.sub(r"\s*\(?\s*base\s*(\d+)\s*\)?\s*$", r"_\1", s, flags=re.I)  # 33033 base 5 vs 33033_5
    s = re.sub(r"\\(?:left|right)\b|\\[,;:! ]", "", s)
    while True:
        new = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"\1/\2", s)
        if new == s:
            break
        s = new
    s = re.sub(r"[{}\s]", "", s)
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s)
    s = s.rstrip(".")
    s = re.sub(r"(?<![\d.])0(?=\.\d)", "", s)  # 0.46 vs .46
    if s.startswith("(") and s.endswith(")"):  # (4, 1) vs 4, 1
        s = s[1:-1]
    return s.lower()


def bold_values(solution):
    """Contents of every \\mathbf{...}, with nested braces balanced."""
    vals, i = [], 0
    while (i := solution.find("\\mathbf{", i)) >= 0:
        start = j = i + len("\\mathbf{")
        depth = 1
        while j < len(solution) and depth:
            depth += {"{": 1, "}": -1}.get(solution[j], 0)
            j += 1
        vals.append(solution[start:j - 1])
        i = j
    return vals


def final_values(solution):
    """Candidates for a solution's final answer: every bold value, plus each
    token of its last 200 characters before the final "Ans" (the pre-2021
    layout ends "... = 20 Ans." with no bold), or before the end."""
    vals = bold_values(solution)
    cut = [m.start() for m in re.finditer(r"\bAns\b", solution)]
    tail = solution[:cut[-1]] if cut else solution
    tail = re.sub(r"\\(?:underline|textbf|text|mathbf)\{", " ", tail[-200:])
    vals += re.findall(r"\([^()]*\)", tail)[-1:]  # an ordered pair such as (6, 4)
    for tok in re.split(r"\s+|=|\\approx|\$+|\\ |\(|\)", tail):
        tok = tok.strip(".,;:!? ").removesuffix("\\")
        if tok:
            vals.append(tok)
    return vals


def gate(reading, draft, expected, has_solutions, overrides):
    """-> {key: [failure, ...]}; overrides lists failures a person accepted."""
    fails = {}

    def fail(k, kind, detail):
        if kind not in overrides.get(k, []) and kind not in overrides.get("*", []):
            fails.setdefault(k, []).append({"gate": kind, "detail": detail})

    keys = [key_of(p["round"], p["problemNumber"]) for p in draft["problems"]]
    for p in draft["problems"]:
        k = key_of(p["round"], p["problemNumber"])
        content = reading["content"].get(k, "")
        if not content:
            fail(k, "content", "no problem text")
        else:
            covered, faithful = overlap(p["textLayer"], content)
            if faithful < OVERLAP_MIN or covered < COVER_MIN:
                fail(k, "overlap", f"prose overlap: {faithful:.0%} of the reading in the text layer, "
                                   f"{covered:.0%} of the text layer in the reading")
        answer = reading["answers"].get(k)
        if not answer:
            fail(k, "answer", "no answer")
        sol = reading["solutions"].get(k)
        if has_solutions and p["round"] != "countdown":
            if not sol:
                fail(k, "solution", "no solution")
        if sol and answer:
            accepted = [answer] + reading["alternatives"].get(k, [])
            finals = {norm_value(b) for b in final_values(sol)}
            if not finals & {norm_value(a) for a in accepted}:
                fail(k, "final-value", f"answer {answer!r}, solution ends {sorted(finals)}")
    for rnd in ROUNDS:
        want = expected.get(rnd)
        got_p = sum(k.startswith(rnd + "-") for k in keys)
        got_a = sum(k.startswith(rnd + "-") for k in reading["answers"])
        if want is not None and got_p != want:
            fail(f"{rnd}-*", "count", f"{got_p} Problems, metadata says {want}")
        if want is not None and got_a != want:
            fail(f"{rnd}-*", "count", f"{got_a} answers, metadata says {want}")
    for k in reading["answers"]:
        if k not in keys:
            fail(k, "count", "answer for a Problem not in the draft")
    return fails


# --------------------------------------------------------------------------
# One Test


class Test:
    def __init__(self, work, rounds=None):
        self.work = Path(work)
        self.name = self.work.name
        self.draft = json.loads((self.work / "draft.json").read_text())
        review_path = self.work / "review.json"
        self.review = json.loads(review_path.read_text()) if review_path.exists() else {}
        # skipRounds (e.g. ["countdown"]) leaves those Rounds out entirely: not read, gated or built
        self.skip = set(self.review.get("skipRounds", []))
        self.draft["problems"] = [p for p in self.draft["problems"] if p["round"] not in self.skip]
        # rounds (--rounds countdown): new Rounds on an imported Test; only their crops and the answer pages
        self.rounds = set(rounds) if rounds else None
        if self.rounds:
            if self.rounds & self.skip:
                raise ValueError(f"{self.name}: remove {', '.join(sorted(self.rounds & self.skip))} "
                                 f"from skipRounds in review.json first")
            self.draft["problems"] = [p for p in self.draft["problems"] if p["round"] in self.rounds]
        self.keys = [key_of(p["round"], p["problemNumber"]) for p in self.draft["problems"]]
        self.answer_pages = sorted((self.work / "pages").glob("answers-p*.png"), key=page_no)
        self.solution_pages = sorted((self.work / "pages").glob("solutions-p*.png"), key=page_no)
        if self.rounds:
            self.solution_pages = []
        # pageOrder: {"solutions": [1, ..., 15, 17, 16]} for scans with pages out of sequence
        for kind, order in self.review.get("pageOrder", {}).items():
            pages = getattr(self, f"{kind[:-1]}_pages")
            rank = {n: i for i, n in enumerate(order)}
            pages.sort(key=lambda p: rank.get(page_no(p), len(order) + page_no(p)))
        # visionCorrections: {"answers": {"team-09": "381,649"}, ...}, hand fixes applied over the reading
        self.corrections = self.review.get("visionCorrections", {})
        self.figure_keys = set(self.review.get("solutionFigures", {}))
        self.overrides = self.review.get("visionOverrides", {})
        self.warnings = [] if review_path.exists() else ["no review.json: counts checked against defaults"]

    def expected_counts(self):
        rounds = self.review.get("metadata", {}).get("rounds")
        if rounds:
            return {r: v["problem_count"] for r, v in rounds.items()
                    if "problem_count" in v and self.kept(r + "-")}
        counts = dict(DEFAULT_COUNTS)
        counts = {r: n for r, n in counts.items() if any(k.startswith(r + "-") for k in self.keys)}
        return counts

    def kept(self, key):
        rnd = key.split("-")[0]
        return rnd not in self.skip and (self.rounds is None or rnd in self.rounds)

    def jobs(self, keys=None, answer_pages=None, solution_pages=None):
        out = []
        for k in self.keys if keys is None else keys:
            out.append(("problem", k, self.work / "crops" / f"{k}.png", PROBLEM_PROMPT))
        for p in self.answer_pages if answer_pages is None else answer_pages:
            out.append(("answers", p.name, p, ANSWER_PROMPT))
        for p in self.solution_pages if solution_pages is None else solution_pages:
            out.append(("solutions", p.name, p, SOLUTION_PROMPT))
        return out

    def assemble(self, results):
        content = {k: demath(tidy(results[("problem", k)])) for k in self.keys if results.get(("problem", k))}
        answers, alternatives, a_src, w1 = assemble_answers(
            [(p.name, results.get(("answers", p.name))) for p in self.answer_pages])
        solutions, s_src, w2 = assemble_solutions(
            [(p.name, results.get(("solutions", p.name))) for p in self.solution_pages],
            self.figure_keys)
        kept = self.kept
        answers = {k: a for k, a in answers.items() if kept(k)}
        alternatives = {k: a for k, a in alternatives.items() if kept(k)}
        solutions = {k: tidy(t) for k, t in solutions.items() if kept(k)}
        for field, fixes in (("content", content), ("answers", answers),
                             ("alternatives", alternatives), ("solutions", solutions)):
            if field == "solutions":  # after the answer corrections, before the solution ones
                fixes.update({k: bold_final(t, [answers[k]] + alternatives.get(k, []))
                              for k, t in fixes.items() if k in answers})
            fixes.update(self.corrections.get(field, {}))
        return {"content": content, "answers": answers, "alternatives": alternatives,
                "solutions": solutions, "answerSource": a_src, "solutionSource": s_src,
                "warnings": w1 + w2}

    def gate(self, reading):
        return gate(reading, self.draft, self.expected_counts(), bool(self.solution_pages), self.overrides)


def run_jobs(client, test, model, jobs, concurrency):
    results = {}
    with cf.ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(client.complete, test.name, model, prompt, image): (kind, ident)
                   for kind, ident, image, prompt in jobs}
        try:
            for f in cf.as_completed(futures):
                results[futures[f]] = f.result()
        except BaseException:
            for f in futures:
                f.cancel()
            raise
    return results


def neighbour_pages(test, key, source, pages):
    """Pages to re-read for a failed key with no source: from its nearest
    earlier sourced neighbour's page to its nearest later one's, inclusive.
    Every page when neither neighbour has a source (#38)."""
    names = [p.name for p in pages]
    first_page = lambda k: (source[k] if isinstance(source[k], str) else source[k][0])
    last_page = lambda k: (source[k] if isinstance(source[k], str) else source[k][-1])
    order = test.keys
    i = order.index(key) if key in order else None
    before = next((k for k in reversed(order[:i]) if k in source), None) if i is not None else None
    after = next((k for k in order[i + 1:] if k in source), None) if i is not None else None
    if before is None and after is None:
        return set(names)
    lo = names.index(last_page(before)) if before else 0
    hi = names.index(first_page(after)) if after else len(names) - 1
    return set(names[min(lo, hi):max(lo, hi) + 1])


def reread_jobs(test, reading, fails):
    keys, a_pages, s_pages = set(), set(), set()
    for k, items in fails.items():
        kinds = {i["gate"] for i in items}
        if k.endswith("-*"):
            a_pages.update(p.name for p in test.answer_pages)
            continue
        if kinds & {"content", "overlap"}:
            keys.add(k)
        if kinds & {"answer", "final-value", "count"}:
            src = reading["answerSource"].get(k)
            a_pages.update([src] if src else neighbour_pages(test, k, reading["answerSource"], test.answer_pages))
        if kinds & {"solution", "final-value"}:
            src = reading["solutionSource"].get(k)
            s_pages.update(src if src else neighbour_pages(test, k, reading["solutionSource"], test.solution_pages))
    return test.jobs(
        keys=[k for k in test.keys if k in keys],
        answer_pages=[p for p in test.answer_pages if p.name in a_pages],
        solution_pages=[p for p in test.solution_pages if p.name in s_pages])


def merge_reread(first, second, keys):
    merged = {f: dict(first[f]) for f in ("content", "answers", "alternatives", "solutions",
                                          "answerSource", "solutionSource")}
    merged["warnings"] = list(first["warnings"])
    for k in keys:
        for f in ("content", "answers", "alternatives", "solutions"):
            if k in second[f]:
                merged[f][k] = second[f][k]
            elif f == "alternatives":
                merged[f].pop(k, None)
    return merged


def write_json(path, data):
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n")


def timed_jobs(client, test, spec, jobs, concurrency, wall, name):
    t0 = time.time()
    results = run_jobs(client, test, spec, jobs, concurrency or CONCURRENCY[parse_spec(spec)[0]])
    wall[name] = round(wall.get(name, 0.0) + time.time() - t0, 1)
    return results


def process(test, client, args):
    print(f"== {test.name}: {len(test.keys)} Problems, {len(test.answer_pages)} answer pages, "
          f"{len(test.solution_pages)} solution pages" + (f" (rounds {','.join(sorted(test.rounds))})"
                                                          if test.rounds else ""))
    wall = {}
    jobs = test.jobs()
    if args.sample:
        jobs = random.Random(test.name).sample(jobs[:len(test.keys)], min(args.sample, len(test.keys)))
    first = timed_jobs(client, test, args.model, jobs, args.concurrency, wall, "read")
    if args.dry_run:
        print(f"   {sum(v is None for v in first.values())} uncached calls, "
              f"{sum(v is not None for v in first.values())} cached (read only)")
        return
    vdir = test.work / args.out
    if args.sample:
        out = vdir / "sample.json"
        out.parent.mkdir(exist_ok=True)
        write_json(out, {k[1]: v for k, v in sorted(first.items())})
        print(f"   wrote {out}")
        return

    reading = test.assemble(first)
    fails = test.gate(reading)
    fell = []
    if fails and args.fallback:
        jobs2 = reread_jobs(test, reading, fails)
        print(f"   {len(fails)} keys failed a gate; re-reading {len(jobs2)} images with {args.fallback}")
        second_results = dict(first)
        second_results.update(timed_jobs(client, test, args.fallback, jobs2, args.concurrency, wall, "fallThrough"))
        second = test.assemble(second_results)
        tried = sorted(k for k in fails if not k.endswith("-*"))
        if any(k.endswith("-*") for k in fails):
            tried += sorted(k for k in second["answers"] if reading["answers"].get(k) != second["answers"][k])
        merged = merge_reread(reading, second, tried)
        fell = sorted(k for k in set(tried) if any(merged[f].get(k) != reading[f].get(k)
                                                   for f in ("content", "answers", "alternatives", "solutions")))
        fails_after = test.gate(merged)
        failures = {k: {"failures": v,
                        "local": {f: reading[f].get(k) for f in ("content", "answers", "solutions")},
                        "kimi": {f: second[f].get(k) for f in ("content", "answers", "solutions")},
                        "crop": f"crops/{k}.png" if k in test.keys else None}
                    for k, v in fails_after.items()}
        reading, fails = merged, fails_after
    else:
        failures = {k: {"failures": v} for k, v in fails.items()}

    vdir.mkdir(exist_ok=True)
    for f in ("content", "answers", "alternatives", "solutions"):
        path = vdir / f"{f}.json"
        data = reading[f]
        if test.rounds and path.exists():  # keep the reading of the Rounds not re-read
            data = merge_keys(json.loads(path.read_text()), data, test)
        write_json(path, dict(sorted(data.items())))
    spot = sorted(set(random.Random(test.name).sample(test.keys, min(SPOT_CHECK, len(test.keys))))
                  | set(fell))
    cost = client.test_cost.get(test.name, 0.0)
    calls = {b: c for (t, b), c in sorted(client.test_calls.items()) if t == test.name}
    report = {"test": test.name, "rounds": sorted(test.rounds) if test.rounds else None,
              "read": full_spec(args.model), "fallThrough": full_spec(args.fallback) if args.fallback else None,
              "kimiCost": round(cost, 4), "wallSeconds": wall, "calls": calls,
              "gatesPassed": not fails, "failed": sorted(fails), "fellThrough": fell, "spotCheck": spot,
              "warnings": test.warnings + reading["warnings"]}
    write_json(vdir / (f"report-{'-'.join(sorted(test.rounds))}.json" if test.rounds else "report.json"), report)
    fpath = (test.work if args.out == "vision" else vdir) / "failures.json"
    if fails:
        write_json(fpath, failures)
    elif fpath.exists():
        fpath.unlink()
    print(f"   Kimi ${cost:.2f}; wall {', '.join(f'{k} {v:.0f}s' for k, v in wall.items())}; gates "
          f"{'passed' if not fails else f'FAILED for {len(fails)} keys ({fpath.name})'}; "
          f"fell through {len(fell)}; spot-check {', '.join(spot)}")
    for w in report["warnings"]:
        print(f"   warning: {w}")

    if args.calibrate:
        calibrate(test, reading, vdir, args.reference)
    if args.write:
        write_review_files(test, reading, fails)


def merge_keys(existing, new, test):
    """Existing keys outside the re-read Rounds stay as they are; the re-read
    Rounds' keys are replaced by the new reading."""
    out = {k: v for k, v in existing.items() if not test.kept(k)}
    out.update(new)
    return out


def write_review_files(test, reading, fails):
    if fails:
        print("   not writing: gates failed")
        return
    hand = [p.name for pat in ("content-*.json", "answers-*.json", "sol-*.json")
            for p in test.work.glob(pat) if not p.stem.endswith("-vision")]
    if hand:
        print(f"   not writing: hand-made review files exist ({', '.join(sorted(hand))})")
        return
    names = {"content": "content-vision.json", "answers": "answers-vision.json",
             "solutions": "sol-vision.json", "alternatives": "alternatives-vision.json"}
    for f, name in names.items():
        data = reading[f]
        path = test.work / name
        if test.rounds and path.exists():  # merge: the Kimi keys of the other Rounds are left as they are
            data = merge_keys(json.loads(path.read_text()), data, test)
        write_json(path, dict(sorted(data.items())))
    print(f"   {'merged into' if test.rounds else 'wrote'} {', '.join(names.values())}")


# --------------------------------------------------------------------------
# Calibration against the pilot's hand-verified files (#19)


def calibrate(test, reading, vdir, reference="pilot"):
    """reference "pilot": the hand-verified files; "kimi": the imported
    *-vision.json files, so the result is a per-key disagreement with Kimi,
    not accuracy."""
    def hand(pattern):
        out = {}
        for p in sorted(test.work.glob(pattern)):
            if p.stem.endswith("-vision") == (reference == "kimi"):
                out.update(json.loads(p.read_text()))
        return out

    ref = {f: {k: v for k, v in hand(pat).items() if test.kept(k)}
           for f, pat in (("content", "content-*.json"), ("answers", "answers-*.json"), ("solutions", "sol-*.json"))}
    def squash(s):
        """Whitespace and interchangeable LaTeX spellings don't count as differences."""
        s = re.sub(r"\\dfrac", r"\\frac", tidy(s or ""))
        s = re.sub(r"\\(le|ge)q\b", r"\\\1", s)
        return re.sub(r"\s+", "", s)

    lines = [f"# Calibration: {test.name} (against {reference})", ""]
    bar = {}
    for f in ("answers", "content", "solutions"):
        keys = sorted(ref[f])
        exact = [k for k in keys if squash(reading[f].get(k)) == squash(ref[f][k])]
        if f == "answers":
            exact = [k for k in keys if norm_value(reading[f].get(k)) == norm_value(ref[f][k])
                     or squash(reading[f].get(k)) == squash(ref[f][k])]
        bar[f] = (len(exact), len(keys))
        lines.append(f"- {f}: {len(exact)}/{len(keys)} match ({len(exact) / max(len(keys), 1):.1%})")
    a, n = bar["answers"]
    c, m = bar["content"]
    lines += ["", f"Bar: answers {a}/{n} (need all), content {c / max(m, 1):.1%} (need 95%), "
                  f"then every difference judged by hand.", ""]
    for f in ("answers", "content", "solutions"):
        diffs = [k for k in sorted(ref[f]) if squash(reading[f].get(k)) != squash(ref[f][k])]
        if diffs:
            lines.append(f"## {f} differences ({len(diffs)})")
            lines.append("")
            for k in diffs:
                lines += [f"### {k}", "", f"{reference}:", "", "    " + (ref[f][k] or "").replace("\n", "\n    "),
                          "", "vision:", "", "    " + (reading[f].get(k) or "(missing)").replace("\n", "\n    "), ""]
    out = vdir / "calibration.md"
    out.write_text("\n".join(lines) + "\n")
    write_json(vdir / "calibration.json", {f: {"match": bar[f][0], "of": bar[f][1],
               "diff": [k for k in sorted(ref[f]) if squash(reading[f].get(k)) != squash(ref[f][k])]}
               for f in bar})
    print(f"   calibration: answers {a}/{n}, content {c}/{m}, solutions "
          f"{bar['solutions'][0]}/{bar['solutions'][1]} -> {out}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("work", nargs="+", help="extract.py work directories")
    ap.add_argument("--model", help=f"read model spec (default MATHCOUNTS_VISION_MODEL, else {PRIMARY})")
    ap.add_argument("--fallback", help=f"fall-through model spec; \"\" turns it off "
                                       f"(default MATHCOUNTS_VISION_FALLBACK, else {FALLBACK})")
    ap.add_argument("--rounds", help="comma list: read only these Rounds' crops and the answer pages, "
                                     "and merge them into the review files (e.g. countdown)")
    ap.add_argument("--concurrency", type=int, help=f"parallel calls (default {CONCURRENCY})")
    ap.add_argument("--calibrate", action="store_true", help="compare with --reference")
    ap.add_argument("--reference", choices=["pilot", "kimi"], default="pilot",
                    help="what --calibrate compares with: the hand-verified pilot files or the imported Kimi files")
    ap.add_argument("--out", default="vision", help="output directory name inside each work dir")
    ap.add_argument("--write", action="store_true", help="write the *-vision.json review files if gates pass")
    ap.add_argument("--dry-run", action="store_true", help="count cached and uncached calls; no API calls")
    ap.add_argument("--sample", type=int, default=0, help="read N random Problem crops only, to try the prompt")
    args = ap.parse_args(argv)
    args.model = choose(args.model, "MATHCOUNTS_VISION_MODEL", PRIMARY)
    args.fallback = choose(args.fallback, "MATHCOUNTS_VISION_FALLBACK", FALLBACK)
    if not args.model:
        sys.exit("no read model: pass --model or set MATHCOUNTS_VISION_MODEL")
    if args.write and args.out != "vision":
        sys.exit("--write needs --out vision: other output dirs are for comparisons only")
    rounds = [r.strip() for r in args.rounds.split(",") if r.strip()] if args.rounds else None
    if rounds and set(rounds) - set(ROUNDS):
        sys.exit(f"--rounds: unknown Round {', '.join(sorted(set(rounds) - set(ROUNDS)))}")

    key = load_key()
    uses_openrouter = any(parse_spec(m)[0] == "openrouter" for m in (args.model, args.fallback) if m)
    if uses_openrouter and not key and not args.dry_run:
        sys.exit("OPENROUTER_API_KEY is not set (environment or .env); "
                 "it is needed for " + " and ".join(m for m in (args.model, args.fallback)
                                                    if m and parse_spec(m)[0] == "openrouter"))
    client = Client(key, dry_run=args.dry_run, ollama_url=env_value("OLLAMA_URL"))
    print(f"read {full_spec(args.model)}; fall-through {full_spec(args.fallback) if args.fallback else 'off'}")
    failed = []
    try:
        for work in args.work:
            try:
                test = Test(work, rounds)
            except ValueError as e:
                print(f"   skipped: {e}")
                failed.append(Path(work).name)
                continue
            try:
                process(test, client, args)
            except CapExceeded as e:
                print(f"   stopped: {e}")
                failed.append(test.name)
                if "run cap" in str(e):
                    break
    except OllamaUnavailable as e:
        sys.exit(str(e))
    print(f"run: Kimi ${client.run_cost:.2f}, calls {client.calls}")
    if failed:
        sys.exit(f"not done: {', '.join(failed)}")


if __name__ == "__main__":
    main()
