# MATHCOUNTS vision pass: runbook

`scripts/mathcounts/vision.py` transcribes a Test's Problem crops, answer-key pages and solution pages with a vision model, gates the result, and writes the `*-vision.json` review files that `build_test.py` merges. This page explains how to run it. The script's docstring has the full reference.

Pipeline: `extract.py` → **`vision.py`** → `build_test.py` → `npm run import:mathcounts`.

## Models

| Pass | Default spec | Cost |
|---|---|---|
| Read | `ollama:qwen3.6:27b-q8_0` (local) | free |
| Fall-through: one try per key that fails a gate | `openrouter:moonshotai/kimi-k3.1-pro` | Kimi spend, capped at $5 per Test and $100 per run |

A spec is `backend:model`. A bare name means `openrouter:`. Each pass is chosen by a flag, then an environment variable (or the repo's `.env`), then the default:

| Flag | Variable |
|---|---|
| `--model` | `MATHCOUNTS_VISION_MODEL` |
| `--fallback` (`""` turns it off) | `MATHCOUNTS_VISION_FALLBACK` |
| — | `OLLAMA_URL` (default `http://127.0.0.1:11435/v1`) |
| — | `OPENROUTER_API_KEY` (needed only when a pass uses OpenRouter) |

For a one-off all-Kimi run, pass `--model openrouter:moonshotai/kimi-k3.1-pro`.

## 1. Start the Ollama server

`vision.py` doesn't start Ollama. Before the first uncached call it checks the server and the model, and stops with the command to run if either is missing. Run the server in its own terminal:

```
OLLAMA_HOST=127.0.0.1:11435 OLLAMA_CONTEXT_LENGTH=16384 OLLAMA_NUM_PARALLEL=3 OLLAMA_KEEP_ALIVE=30m ollama serve
```

- Use port 11435, not the Ollama app's own server on 11434. The app's server defaults to a 262k context.
- Parallel 3 is the measured setting on the dev Mac (M4 Pro, 64 GB): about 1.75× parallel 1, with no swap. `vision.py` matches it with 3 concurrent Ollama calls (8 for OpenRouter); `--concurrency` overrides both.
- If the model is missing: `OLLAMA_HOST=127.0.0.1:11435 ollama pull qwen3.6:27b-q8_0`.

## 2. Run

```
python3 -I scripts/mathcounts/vision.py crawled_data/mathcounts/_work/<test> [more ...] --dry-run   # count uncached calls
python3 -I scripts/mathcounts/vision.py crawled_data/mathcounts/_work/<test> --write
```

`--write` writes the review files only if every gate passes. It refuses when hand-made review files exist (the pilot) and when `--out` isn't `vision`.

Rough times at parallel 3: about 10 s per Problem crop, 25 s per answer page, 70 s per solution page. A Chapter-sized Test takes about 25 min. Every response is cached in `_work/_vision-cache/`, so a re-run never pays twice.

### Long runs

- Start them in their own session so they outlive the terminal or agent session that launched them. `nohup … & disown` isn't enough:

  ```
  python3 -c "import os,sys; os.setsid(); os.execvp(sys.argv[1], sys.argv[1:])" nohup python3 -I scripts/mathcounts/vision.py ... > run.log 2>&1 &
  ```

- To stop a run, interrupt the `python3 vision.py` process itself, not a shell wrapper; otherwise two runs end up sharing the server's slots.
- Resuming is just running the same command again. An interruption loses at most the calls in flight.

## 3. Add Rounds to an imported Test (Countdown)

The imported Tests were read by Kimi without Countdown. To add it:

1. Remove `countdown` from `skipRounds` in the Test's `review.json`.
2. Run `vision.py <work> --rounds countdown --write`.
   - This reads only the Countdown crops plus the answer pages; solution pages are skipped.
   - The gates run only on Countdown.
   - The new keys are merged into the existing `*-vision.json` files. Kimi's keys for the other Rounds are left exactly as they are.
3. Run `build_test.py`, then `npm run import:mathcounts`.

## 4. When a gate fails

The run writes `<work>/failures.json`. For each failed key it records the gate, the local reading, the Kimi reading and the crop. For each key, choose one of these fixes in `review.json`:

- **The reading is right and the gate is wrong.** This happens, for example, when the PDF text layer runs letters together and the prose-overlap gate fails. Accept the failure:

  ```json
  "visionOverrides": {"countdown-80": ["overlap"]}
  ```

- **A misread.** Correct the value:

  ```json
  "visionCorrections": {"answers": {"team-09": "381,649"}}
  ```

- **Scanned pages out of order.** Reorder them:

  ```json
  "pageOrder": {"solutions": [1, 2, 15, 17, 16]}
  ```

Then re-run. It's free, since every read is cached.

## Outputs

In `<work>/vision/` (or `--out DIR`):

- **Reading files:** `content.json`, `answers.json`, `alternatives.json`, `solutions.json`.
- **`report.json`:** written with `--rounds`, it's `report-<rounds>.json`. It records:
  - `read` and `fallThrough`, the specs used;
  - `fellThrough`, the keys whose final reading came from Kimi;
  - `kimiCost`, and `wallSeconds` per pass;
  - `calls` per backend;
  - the gates, the spot-check list (5 random keys plus every fall-through key), and warnings.
- **`calibration.md` and `calibration.json`:** with `--calibrate`. `--reference pilot` compares with the hand-verified pilot files. `--reference kimi` compares with the imported Kimi files, which gives a per-key disagreement check rather than accuracy. Use a scratch `--out` for comparisons.

## Shared format fixes

These run in code on every model's reading, Kimi's included:

- Round labels only move forward.
- A repeated item number is stripped from a Solution.
- Plain values in Problem text are taken out of math: numbers, point names of 2+ letters, measurements, units, percents and dollar amounts.
- In the pre-2021 "Ans." layout, the value before "Ans." is bolded when the answer key confirms it.

Tests: `python3 -I -m unittest discover -s scripts/mathcounts -p 'test_*.py'`.
