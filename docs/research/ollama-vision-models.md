# Ollama vision models for MATHCOUNTS pages on a 64 GB M4 Pro

Research for issue #34 (map #33). Written 2026-11-23 against Ollama v0.40.17, which is both the installed version and the latest release (released 2026-11-10). Source code is cited at `ollama/ollama@318ee28` (main, 2026-11-22). Nothing was pulled or run; this is reading only.

**Short answer.** Bake off these three, in this order:

| # | Ollama tag | Quant | Download | Why |
|---|---|---|---|---|
| 1 | `qwen3.6:27b-q8_0` (or `qwen3.6:27b-mtp-q8_0` for speculative decoding) | Q8_0 | 30 GB | It has the best independent OCR score of any model that fits: OCRBench v2 English 68.3, ahead of Qwen3.8-27B at 63.5. Vendor OmniDocBench 1.5 is 89.4. It is dense, so there is no MoE routing noise. |
| 2 | `qwen3.8:27b-q8_0` (or `qwen3.8:27b-mtp-q8_0`) | Q8_0 | 30 GB | It is the newest Qwen and has the best vendor document and math-vision numbers that fit: OmniDocBench 1.5 91.1, MathVision 90.0. The independent board puts it below 3.6, so the bake-off has to settle which is better. |
| 3 | `gemma4:31b-it-q8_0` (`gemma4:31b-it-q4_K_M` at 20 GB if memory is tight) | Q8_0 | 34 GB | It is a different family, which matters for the disagreement check. Vendor OmniDocBench 1.5 edit distance is 0.131 against 0.365 for the installed `gemma3:27b`, and MATH-Vision is 85.6. Image resolution is dynamic, up to 1120 tokens. |

Pull them one at a time. Two Q8 models plus KV cache won't fit together, as explained under memory below.

There are two alternates, both rejected for now. `inkling-2-mini` was released 3 days ago and is fast (MoE, 5.4B active), with OmniDocBench v1.6 92.8. But its own card warns it "is more likely than larger models to state incorrect information with confidence", and its reasoning cannot be fully disabled. Both are bad signs for the errata gate. `glm-ocr` scores highest on OmniDocBench (94.62 v1.5), but it is a 0.9B task-prompted OCR specialist and cannot follow the Kimi prompts' LaTeX and format rules.

**API facts that change the bake-off plan (#35):**

1. `vision.py`'s request works unchanged against `http://localhost:11434/v1/chat/completions`, including the nested `image_url: {url: "data:image/png;base64,…"}` part. Unknown fields such as `usage: {include: true}` are ignored.
2. **Pass `presence_penalty: 0` explicitly.** The installed `qwen3.5` ships `presence_penalty 1.5` in its params, and Ollama applies penalties even under greedy decoding. That would push a transcriber away from repeating digits, `$` and words. `qwen3.6` and `qwen3.8` ship 0, but don't depend on it.
3. **Disable thinking with `reasoning_effort: "none"`.** Reasoning comes back in `message.reasoning`, separate from `content`. It still counts toward `max_tokens` and costs wall time.
4. **`num_ctx` cannot be set per request on `/v1`.** Set `OLLAMA_CONTEXT_LENGTH` on the server, or make a derived model with a Modelfile. Without it, this Mac may allocate up to 256k per slot.
5. **Concurrency 8 with a 300 s timeout will time out.** Requests beyond `OLLAMA_NUM_PARALLEL` queue silently, and a dense 27B decodes at roughly 7–13 tok/s on this machine. Match `--concurrency` to the server's parallel slots and raise the timeout.
6. **Cost.** The response has no `usage.cost`, so `price()` will call OpenRouter's `/models` for an unknown model id and return 0. The backend should short-circuit cost to 0.

## The machine

- **Chip:** Apple M4 Pro with 64 GB (`sysctl hw.memsize` = 68719476736).
- **Memory bandwidth:** Apple quotes "up to 64GB of fast unified memory and 273GB/s of memory bandwidth" ([Apple newsroom, Oct 2024](https://www.apple.com/newsroom/2024/10/apple-introduces-m4-pro-and-m4-max/)).
- **Decode speed:** token generation on Apple silicon is memory-bandwidth bound, so the ceiling is about 273 GB/s divided by the bytes of weights read per token. The tokens/s figures below are derived from that and are not measured. No primary source publishes M4 Pro numbers for these models. Ollama returns a `timings` object on every `/v1` response (`predicted_per_second`, `prompt_per_second`; [`openai/openai.go`](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/openai/openai.go#L134-L143)), so #35 can measure them for free.
- **GPU memory share:** macOS lets the GPU wire only part of unified memory. `iogpu.wired_limit_mb` is 0 here, meaning the OS default. I did not find a primary source for the exact default share, so check `ollama ps` after the first load (see [memory](#memory-and-context)).

## Candidates

### Evidence available

The vendor numbers are not comparable across vendors. Muse Glimmer's card scores Qwen3.6-27B at 77.8 on OmniDocBench v1.5, but Qwen's own card scores it at 89.4. Gemma reports edit distance (lower is better), and Inkling reports v1.6. The only independent, same-harness comparison found is OCRBench v2 (2026.09 round). It has no entries for Gemma 4 31B, Inkling or GLM-OCR.

| Model (Ollama) | Params | OCRBench v2 EN / ZH (independent) | OmniDocBench (vendor) | Math vision (vendor) | Source |
|---|---|---|---|---|---|
| `qwen3.6:27b` | 27.3B dense | **68.3** / 58.7 | 89.4 (v1.5, Qwen card) | – | [OCRBench v2](https://99franklin.github.io/ocrbench_v2/), [Qwen3.8 card](https://huggingface.co/Qwen/Qwen3.8-27B) |
| `qwen3.8:27b` | 27.3B dense | 63.5 / 56.9 | 91.1 (v1.5) | MathVision 90.0 (no CI) | same |
| `gemma4:31b` | 30.7B dense | not listed | 0.131 edit dist. (v1.5) | MATH-Vision 85.6 | [ollama.com/library/gemma4](https://ollama.com/library/gemma4) |
| `gemma3:27b` (installed) | 27.4B dense | not listed | 0.365 edit dist. (v1.5) | MATH-Vision 46.0 | same (Gemma 4 card's baseline column) |
| `inkling-2-mini` | 26B MoE, 5.4B active | not listed | 92.8 (v1.6) | MathVision 89.0 | [Thinking Machines card](https://thinkingmachines.ai/model-card/inkling-2-mini/) |
| `qwen3.6:35b-a3b` | 35B MoE, ~3B active | 65.5 / 60.8 | – | – | OCRBench v2 |
| `nemotron3:33b` (Nemotron 3 Nano Omni) | 30B A3B | 65.8 / 59.0 | – | – | OCRBench v2, [ollama.com/library/nemotron3](https://ollama.com/library/nemotron3) |
| `muse-glimmer:30b` | 30B | 56.9 / 56.8 | 75.8 (v1.5) | – | OCRBench v2, [ollama.com/library/muse-glimmer](https://ollama.com/library/muse-glimmer) |
| `glm-ocr` | 0.9B | not listed | 94.62 (v1.5) | – | [ollama.com/library/glm-ocr](https://ollama.com/library/glm-ocr) |
| `qwen3.5:latest` (installed, 9.7B) | 9.7B dense | 58.7 / 64.1 (as Qwen3.5-9B) | – | – | OCRBench v2 |

No candidate publishes OCRBench v1 or MathVista any more. MathVision and CharXiv are the math and chart rows the cards actually report.

### 1. `qwen3.6:27b-q8_0`

- **Tags** ([tags page](https://ollama.com/library/qwen3.6/tags)):
  - `27b-q4_K_M` 17 GB
  - `27b-q8_0` 30 GB
  - `27b-mtp-q8_0` 30 GB (multi-token-prediction draft, i.e. speculative decoding)
  - `27b-mxfp8` / `27b-nvfp4` MLX builds
  - 256K context, text and image input.
- **Params shipped:** `presence_penalty 0`, `repeat_penalty 1`, `min_p 0`, `temperature 1` ([ollama.com/library/qwen3.6:27b](https://ollama.com/library/qwen3.6:27b)).
- **Why first:** it has the highest English OCRBench v2 of anything that fits in 64 GB, including above the newer 3.8-27B. On text-recognition-heavy work, independent results beat vendor tables.
- **Image handling:** the Qwen3.x VL processor, with patch 16 and merge 2, so one visual token per 32×32 px. Inputs are bounded between 65,536 and 16,777,216 total pixels (Qwen3.8's [`preprocessor_config.json`](https://huggingface.co/Qwen/Qwen3.8-27B/raw/main/preprocessor_config.json); the family shares it). A 120 DPI answer-key page (about 1020×1320 px) is about 1.3k visual tokens and is read at native resolution, with no downscale.
- **Speed (derived):** Q8 reads about 29 GB per token, so the ceiling is about 9 tok/s and realistic is about 6–8. Q4 is about 11–13 tok/s. The MTP tag should raise either.
- **Weaknesses:**
  - Dense means slow.
  - Thinking is on by default (see [thinking](#thinking-mode)).
  - Not yet measured on these pages.

### 2. `qwen3.8:27b-q8_0`

- **Tags** ([tags page](https://ollama.com/library/qwen3.8/tags)): the same set as 3.6 (`27b-q4_K_M` 18 GB, `27b-q8_0` 30 GB, `27b-mtp-q8_0` 30 GB, MLX `mxfp8`/`nvfp4`/`dflash2-nvfp4`), 256K context.
- **Params shipped:** `presence_penalty 0`, `repeat_penalty 1` ([ollama.com/library/qwen3.8:27b](https://ollama.com/library/qwen3.8:27b)). Model layer Q4_K_M 27.3B plus a 461M BF16 vision projector.
- **Vendor numbers** ([HF card](https://huggingface.co/Qwen/Qwen3.8-27B)): OmniDocBench 1.5 91.1 (3.6-27B: 89.4), MathVision 90.0 / 94.6 with CI, CharXiv RQ 83.7.
- **Why second:** best vendor document score of the Qwen models that fit. The 3.6 vs 3.8 disagreement between vendor and independent boards is the main open question, and only the pilot Test can settle it.
- **Recommended sampling:** the card recommends non-thinking `temperature 0.7, top_p 0.8, presence_penalty 1.5` and says presence_penalty "between 0 and 2 to reduce endless repetition", with the caveat that a higher value "may occasionally result in … a slight decrease in model performance". That advice is aimed at chat. For transcription keep presence_penalty 0, and catch loops with `max_tokens` plus `finish_reason: "length"` instead.
- **Speed and image handling:** same as 3.6.
- **Weaknesses:** independent OCRBench v2 is about 5 points below 3.6. Its model card highlights agentic and coding gains, not OCR.

### 3. `gemma4:31b-it-q8_0`

- **Tags** ([tags page](https://ollama.com/library/gemma4/tags)):
  - `31b-it-q4_K_M` 20 GB
  - `31b-it-qat` 19 GB
  - `31b-it-q8_0` 34 GB
  - `31b-mxfp8` 34 GB
  - `31b-nvfp4` 19 GB (MLX)
  - 256K context. The default `gemma4:31b` also carries a 470M Q8_0 draft layer for speculative decoding.
- **Params shipped:** `temperature 1, top_k 64, top_p 0.95`, with no presence penalty ([ollama.com/library/gemma4:31b](https://ollama.com/library/gemma4:31b)).
- **Vendor numbers** ([ollama.com/library/gemma4](https://ollama.com/library/gemma4)): OmniDocBench 1.5 average edit distance 0.131 (26B A4B: 0.149; Gemma 3 27B: 0.365), MATH-Vision 85.6, MMMU Pro 76.9.
- **Why third:** a non-Qwen reader makes the Kimi disagreement check more informative. It is a large step up from the installed `gemma3:27b`, which has a fixed 896 px input (`gemma3.vision.image_size: 896` in `/api/show`) and reads a full page at a fraction of its resolution.
- **Image handling:** variable aspect ratio and resolution, with token budgets 70/140/280/560/1120. The card says higher budgets suit "OCR, document parsing, and reading small text". The Hugging Face processor defaults to `max_soft_tokens: 280` ([processor_config.json](https://huggingface.co/google/gemma-4-31b-it/raw/main/processor_config.json)). Ollama's MLX runner instead picks dynamically: "the smallest publisher-supported mode that preserves both source dimensions, or the largest mode when none fits" ([`mlxrunner/model/gemma4/process_image.go`](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/mlxrunner/model/gemma4/process_image.go#L62-L64)). At 48 px per soft token (patch 16 × pool 3), 1120 tokens covers about 2.6 MP, so a 1.3 MP answer page is read without downscaling. I verified this only for the MLX runner, not the GGUF `q8_0` path.
- **Prompt order:** the card says to "place image and/or audio content before text in the prompt for best results". `vision.py` sends text first. Swapping the order doesn't change the prompt wording, and #35 could try it if Gemma misses.
- **Speed (derived):** Q8 is about 33 GB per token, so about 6–7 tok/s. Q4 is about 10 tok/s.
- **Weaknesses:**
  - Slowest of the three.
  - With thinking disabled, the 31B "still emit[s] an empty thought block". Ollama's template and parser handle this, but check that `content` comes back clean.

### Considered and set aside

- **`inkling-2-mini`** (Thinking Machines, Apache 2.0, NVFP4-native, 20 GB, 1M context; [card](https://thinkingmachines.ai/model-card/inkling-2-mini/)). It is the fastest strong option (5.4B active, so tens of tok/s) and accepts images from 40 to 4096 px per side. It was released 2026-11-20. Its own card warns of confident hallucination, says "setting reasoning effort to its minimum does not fully disable reasoning", and mentions long reasoning loops. Revisit it only if the dense models are too slow.
- **`glm-ocr`** (0.9B, 1.8–2.7 GB): the top OmniDocBench score, but it is driven by fixed task prefixes (`Text Recognition:`, `Table Recognition:`, `Figure Recognition:`). It is a recogniser, not an instruction follower, so it can't apply `MATH_RULES` (dollar escaping, `\bigstar`, `array` tables, no Markdown). It could serve as a cheap independent check on numbers, but not as a Kimi substitute.
- **`qwen3.6:35b-a3b`, `nemotron3:33b`:** MoE with about 3B active, so about 3× faster than the dense 27B. Their OCRBench v2 is about 3 points below `qwen3.6:27b`. They are a fallback if dense throughput is unacceptable. Nemotron 3 Nano Omni has no published OmniDocBench and its card on Ollama gives no thinking controls.
- **`muse-glimmer:30b`:** weak on both OCRBench v2 (56.9) and OmniDocBench (75.8).
- **Too big for 64 GB:**
  - `qwen3.8-flash-next` (125B, 105 GB MLX)
  - `nemotron-3.5-super` (120B)
  - `ornith-1.5:122b` (73–77 GB)
  - the cloud-only `kimi-k3.1-pro` / `glm-5.3-flash` / `hy4` tags
- **`ornith-1.5:35b`** (23 GB, about 3B active): its card publishes evaluations only as images, so there was no readable evidence.
- **Installed models:**
  - `glm-4.7-flash` has no `vision` capability in `/api/show` and is text-only.
  - `qwen3-coder`, `qwen:14b` and `llama3.2` are text models.
  - `gemma3:27b` is limited to fixed 896 px input.
  - `qwen3.5:latest` (9.7B Q4_K_M) is a usable smoke-test model for wiring, but too small to be the reader.

## API facts (Ollama's `/v1/chat/completions`)

### Does `vision.py`'s request shape work?

Yes, as is. The docs list "Base64 encoded image" as supported and "Image URL" as not ([OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)). The source ([`FromChatRequest`](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/openai/openai.go#L657-L675), [`decodeImageURL`](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/openai/openai.go#L832-L860)) shows:

- **Accepted forms:** `image_url` may be either an object `{"url": …}` (what `vision.py` sends) or a bare string.
- **Accepted prefixes:** `data:image/{jpeg,jpg,png,webp};base64,` or `data:;base64,`. `http(s)://` URLs are rejected with "image URLs are not currently supported".
- **Message splitting:** each content part becomes its own `api.Message` with the same role, so text and image arrive as two consecutive user messages. Only the ordering matters (see the Gemma note above).
- **Ignored fields:** `ChatCompletionRequest` has no `usage` or `options` fields, and Go's decoder drops unknown fields. So `"usage": {"include": True}` is harmless, and an `options: {num_ctx: …}` passed here would be silently ignored.
- **Response:** `choices[0].message.content` holds the answer, and `message.reasoning` holds thinking. `usage` has `prompt_tokens`, `completion_tokens` and `total_tokens`, and there is **no `cost`** ([`ToUsage`](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/openai/openai.go#L263-L274)). `timings` gives tokens/s.
- **Auth:** the client must send some API key, but "Ollama ignores it" (docs). The existing `Authorization: Bearer …` header is fine.

### `temperature: 0` and `seed`

- **Supported fields:** `temperature`, `seed`, `top_p`, `presence_penalty`, `frequency_penalty`, `stop`, `max_tokens`, `response_format` and `reasoning_effort` are listed as supported. The source maps them straight into Ollama `options` ([openai.go L753-L775](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/openai/openai.go#L753-L775)).
- **Temperature 0 is greedy argmax.** In the MLX sampler, `if slot.opts.Temperature == 0 { return …Argmax… }` ([`mlxrunner/sample/sample.go` L812-L815](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/mlxrunner/sample/sample.go#L812-L815)). The seed only matters when temperature is above 0. Repeat runs of the same model, quant and prompt should therefore give the same text.
- **Not determinism-guaranteed:** no Ollama doc promises bit-exact output, and batching several parallel requests can change float rounding (an inference, not documented). The existing response cache makes this moot for re-runs, and #35 can check it by reading the same crop twice.
- **Penalties survive greedy:** "Greedy decoding returns the penalty-adjusted logits" ([sample.go L505](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/mlxrunner/sample/sample.go#L505)). A model's shipped `presence_penalty` still bends greedy output. The installed `qwen3.5` ships `presence_penalty 1.5` (`ollama show qwen3.5 --parameters`). **Send `presence_penalty: 0` in the request** so the result doesn't depend on each package's params.

### Context and output length

- **Context default:** "Ollama defaults to the following context lengths based on VRAM: < 24 GiB VRAM: 4k context; 24-48 GiB VRAM: 32k context; >= 48 GiB VRAM: 256k context" ([Context length](https://docs.ollama.com/context-length)). The env help string agrees: "default: 4k/32k/256k based on VRAM" ([`envconfig/config.go` L338](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/envconfig/config.go#L338)). The older [Modelfile](https://docs.ollama.com/modelfile) table (2048) and [FAQ](https://docs.ollama.com/faq) (4096) are stale. On this Mac the tier depends on how much of the 64 GB Metal reports, so check the CONTEXT column of `ollama ps`.
- **Setting it:** "The OpenAI API does not have a way of setting the context size for a model" (docs). The choices are:
  1. `OLLAMA_CONTEXT_LENGTH=16384 ollama serve`, which is global.
  2. A Modelfile `FROM qwen3.6:27b-q8_0` / `PARAMETER num_ctx 16384`, then `ollama create`, then use that name in `--model`.
  3. Native `/api/chat` with `options.num_ctx`.

  16k is ample. The largest image is about 1.3k visual tokens, the prompt is about 1k, and output is a few thousand without thinking.
- **Output length:** `max_tokens` maps to `num_predict` ([openai.go L753](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/openai/openai.go#L753)). The default `num_predict` is "-1, infinite generation" (Modelfile docs), bounded only by the context. `vision.py` sends no `max_tokens`. **Set one**, about 4096 for a solution page, so a repetition loop ends with `finish_reason: "length"` instead of filling 16k tokens at about 8 tok/s (about 30 minutes).

### `OLLAMA_NUM_PARALLEL` and keep-alive

- **Parallel slots:** `OLLAMA_NUM_PARALLEL`: "When unset or zero, MLX on Metal chooses a conservative default based on available memory and the model's cache requirements; other backends default to 1" ([`docs/faq.mdx`](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/docs/faq.mdx#L363-L367)). So GGUF tags like `-q8_0` get 1 slot by default, and `-mlx`/`-nvfp4`/`-mxfp8` tags get an automatic number.
- **Memory per slot:** "Parallel request processing for a given model results in increasing the context size by the number of parallel requests. For example, a 2K context with 4 parallel requests will result in an 8K context" (same). With a 256k default context, every slot is expensive, which is one more reason to set `OLLAMA_CONTEXT_LENGTH`.
- **Queueing:** extra requests wait silently. `OLLAMA_MAX_QUEUE` defaults to 512, so nothing is rejected.
- **Impact on `vision.py`:** it runs `--concurrency 8` with `urlopen(timeout=300)`. At about 7 tok/s, one solution page of about 1.5k tokens takes about 3.5 min. The 8th queued request then waits well past 300 s, times out and is retried 5 times, duplicating work. For the Ollama backend, set `--concurrency` to the server's slot count (start at 1–2 for a dense Q8 model) and use a timeout of 30 min or more.
- **Keep-alive:** the default is 5 minutes. `OLLAMA_KEEP_ALIVE` takes a duration or seconds, and negative means forever ([config.go L126-L144](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/envconfig/config.go#L126-L144)). The `/v1` request also accepts an Ollama-extension `keep_alive` field. It appears in the source ([openai.go L130-L131](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/openai/openai.go#L130-L131)) but not in the docs. Within one pass the model stays warm. A first read with one local model followed by a re-read with a different one will unload or reload whenever both don't fit.
- **Loaded models:** `OLLAMA_MAX_LOADED_MODELS` defaults to 3, but models load concurrently only if they fit. Two Q8 27–31B models (60+ GB) won't fit, so one is evicted per pass switch. That is fine if passes run sequentially, as `vision.py` already does (all first reads, then re-reads).

### Thinking mode

- **On by default:** all three shortlisted models think by default (Qwen 3.6/3.8: [Ollama card](https://ollama.com/library/qwen3.8); installed `qwen3.5` shows `thinking: {values: [false, true], default: true}` in `/api/show`).
- **Native API:** `think: false` "request[s] no thinking output. Models that cannot disable thinking use their lowest supported level instead" ([Thinking](https://docs.ollama.com/capabilities/thinking)).
- **`/v1` endpoint:** use `reasoning_effort` or `reasoning: {effort}`. `"none"` maps to `think: false` ([`ThinkingFromReasoningEffort`](https://github.com/ollama/ollama/blob/318ee284aa3b5558de57efefff730ea33c4a9bef/openai/openai.go#L584-L617)). Model-defined level names pass through, and `minimal`→`low` and `xhigh`/`ultra`→`max` are aliases. Omitting it leaves the model default, which means thinking is on.
- **Separation:** thinking text comes back in `message.reasoning`, not in `content`, so `strip_fences(content)` is unaffected. Thinking tokens still count toward `max_tokens`/`num_predict` and `completion_tokens`. The "empty reply because reasoning used up the output" retry in `vision.py` stays relevant if thinking is left on.
- **Exceptions:**
  - GPT-OSS cannot disable thinking: `"none"` uses `"low"`.
  - Inkling 2 Mini's minimum effort "does not fully disable reasoning".
  - Gemma 4 31B emits an empty thought block when thinking is off.
- **Recommendation for #35:** read with `reasoning_effort: "none"`. Turn thinking on only as a second arm, if a model misreads layout. Thinking is where "corrections" of errata are most likely to come from, because the model works the Problem.

## Memory and context

These are rough figures for a single slot at a 16k context. They are derived from download size plus KV cache, not measured:

| Model | Weights | KV cache at 16k (f16) | Total | Room for a 2nd slot? |
|---|---|---|---|---|
| `qwen3.6:27b-q8_0` / `qwen3.8:27b-q8_0` | 30 GB | about 1–4 GB (hybrid-attention Qwen3.x keeps a full KV only on some layers) | about 32–34 GB | yes, probably 2 slots |
| `gemma4:31b-it-q8_0` | 34 GB | about 2–4 GB (sliding window 1024 on most layers) | about 37–38 GB | perhaps 1 more |
| `*-q4_K_M` variants | 17–20 GB | same | about 20–24 GB | yes, 2–4 slots |

The KV estimates come from the architectures' sliding-window and hybrid layouts described on the model cards, not from measurement. `ollama ps` shows the real size, processor split and context after load. If it shows any CPU share, drop to Q4 or lower the context. A model that spills from GPU to CPU runs several times slower. `OLLAMA_KV_CACHE_TYPE=q8_0` halves the KV cache when Flash Attention is on ([FAQ](https://docs.ollama.com/faq)). That is a global setting, but there's no reason to need it at 16k.

## Rough wall time per Test

The 2025 Chapter pilot is 128 Problem crops, 6 answer pages and 8 solution pages ([pilot report](mathcounts-2025-chapter-pilot.md)). The estimate assumes no thinking, about 250 output tokens per Problem, about 600 per answer page and about 1,500 per solution page. That is about 32k output tokens for Problems, 3.6k for answers and 12k for solutions, or about 48k in total. At about 7 tok/s (Q8 dense) that is about 2 h, plus prefill of about 1.3k image tokens per page, which is fast at a few hundred tok/s. At about 12 tok/s (Q4 or MTP) it is about 1.1 h. Both fit the map's "1–3 h per Test, overnight" budget. Thinking on would multiply this several times.

## Sources

- Ollama docs:
  - [OpenAI compatibility](https://docs.ollama.com/api/openai-compatibility)
  - [Thinking](https://docs.ollama.com/capabilities/thinking)
  - [Context length](https://docs.ollama.com/context-length)
  - [FAQ](https://docs.ollama.com/faq)
  - [Modelfile](https://docs.ollama.com/modelfile)
- Ollama source at [`318ee28`](https://github.com/ollama/ollama/tree/318ee284aa3b5558de57efefff730ea33c4a9bef):
  - `openai/openai.go`
  - `mlxrunner/sample/sample.go`
  - `mlxrunner/model/gemma4/process_image.go`
  - `envconfig/config.go`
  - `docs/faq.mdx`
- Ollama library pages:
  - [qwen3.6 tags](https://ollama.com/library/qwen3.6/tags)
  - [qwen3.8](https://ollama.com/library/qwen3.8) and [tags](https://ollama.com/library/qwen3.8/tags)
  - [gemma4](https://ollama.com/library/gemma4) and [tags](https://ollama.com/library/gemma4/tags)
  - [inkling-2-mini](https://ollama.com/library/inkling-2-mini)
  - [glm-ocr](https://ollama.com/library/glm-ocr)
  - [muse-glimmer](https://ollama.com/library/muse-glimmer)
  - [nemotron3](https://ollama.com/library/nemotron3)
  - [ornith-1.5](https://ollama.com/library/ornith-1.5)
  - [qwen3.8-flash-next](https://ollama.com/library/qwen3.8-flash-next)
  - [vision search](https://ollama.com/search?c=vision)
- Model cards:
  - [Qwen/Qwen3.8-27B](https://huggingface.co/Qwen/Qwen3.8-27B) (and its `preprocessor_config.json`)
  - [google/gemma-4-31b-it processor_config.json](https://huggingface.co/google/gemma-4-31b-it/raw/main/processor_config.json)
  - [Thinking Machines Inkling 2 Mini](https://thinkingmachines.ai/model-card/inkling-2-mini/)
- Independent benchmark: [OCRBench v2 leaderboard](https://99franklin.github.io/ocrbench_v2/) (2026.09 round).
- Hardware: [Apple M4 Pro announcement](https://www.apple.com/newsroom/2024/10/apple-introduces-m4-pro-and-m4-max/).
- Local, read-only: `ollama --version` (0.40.17), `ollama list`, `/api/show` for the installed models, `ollama show qwen3.5 --parameters`.
