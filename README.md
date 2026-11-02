# GLM-5.3-Tokenizer-Korean

CLI to find out why Korean text shows broken characters (U+FFFD) when streaming from
byte-level BPE models, and to compare three tokenizers on Korean, Hanja and Chinese.
Most Hangul syllables are 3 UTF-8 bytes and are split across several tokens. A client that
decodes each token alone prints U+FFFD.

Analysis (Korean, with diagrams): [docs/hangul-vs-han-tokenization.md](docs/hangul-vs-han-tokenization.md).

## Models

Each model is pinned to a Hub commit. Special tokens are not needed for this analysis, so
encoding never adds them (Kimi-K3 is built with no special tokens).

| Key | Repo | Revision | Format |
|-----|------|----------|--------|
| `glm-5.3` | [zai-org/GLM-5.3](https://huggingface.co/zai-org/GLM-5.3/tree/ba32f8c19c8738e2c57c71798c601d477a7bf844) | `ba32f8c` | `tokenizer.json` (tokenizers) |
| `deepseek-v4.1-flash` | [deepseek-ai/DeepSeek-V4.1-Flash](https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash/tree/314113f8a7dadb388215396ba5fbee2c610a04d6) | `314113f` | `tokenizer.json` (tokenizers), byte-level BPE |
| `kimi-k3` | [moonshotai/Kimi-K3](https://huggingface.co/moonshotai/Kimi-K3/tree/f831ab66814297da540d832a5235f8e904f29d06) | `f831ab6` | `tiktoken.model` (tiktoken) |

Files go to `tokenizers/<key>/` (git-ignored). The old `./tokenizer/` directory is still used
for `glm-5.3` when `tokenizers/glm-5.3/` does not exist. For Kimi, `fetch` also saves
`tokenization_kimi.py` as reference data. This tool never imports or runs it. The Kimi
pre-tokenizer pattern is copied from that file at the pinned revision into
`src/glm_ko_tok/backend_tiktoken.py`.

## Install

```bash
uv sync
uv run glm-ko-tok fetch --model all   # or one key; default glm-5.3
```

## Commands

Every analysis command takes `--model KEY` (repeatable, or `all`; default `glm-5.3`) and
`--root DIR` (default `tokenizers`). With several models, text output has one `== key ==`
section per model and `--json` returns an object keyed by model.

| Command | Purpose |
|---------|---------|
| `fetch [--model M] [--root D]` | Download only the tokenizer files at the pinned revision |
| `coverage [--model M] [--json]` | Hangul syllables that are 1/2/3/4+ tokens, and inside vocab tokens |
| `compare [--model M] [--json]` | Token cost of Hangul, Hanja, GB2312, CJK, jamo; vocab; samples; pre-tokenizer |
| `analyze TEXT` or `--file F [--per-line] [--model M] [--json]` | Per-token bytes, validity, split characters |
| `stream-sim TEXT` or `--file F [--per-line] [--model M] [--json]` | Naive vs incremental vs `DecodeStream` decoding |
| `probe ...` | Capture a real streaming response and check for U+FFFD |

`compare` prints per model: the 1/2/3/4+ token table for each character set, vocab size,
vocab tokens with Hangul, Han and invalid UTF-8 alone, totals on `samples/korean.txt`
(tokens, tokens per non-space character, naive-decode U+FFFD), ko vs zh tokens per character
on `samples/parallel_ko_zh.txt` (`ko<TAB>zh` per line), and the pre-tokenizer regex with a
note on whether it has an explicit Han class or range and any Hangul range. With several
models it adds a summary table (rows = character sets, columns = models, cell = 1-token %).

`stream-sim` on a tiktoken model (Kimi-K3) decodes each token's bytes alone for the naive
case and uses a UTF-8 incremental decoder for the fixed case. `DecodeStream` exists only in
`tokenizers`, so it is reported as skipped there.

Sample inputs: `samples/korean.txt` (`#` lines are comments). Example:

```bash
uv run glm-ko-tok analyze '안녕하세요' --model all
uv run glm-ko-tok stream-sim --file samples/korean.txt --per-line --model all
uv run glm-ko-tok compare --model all
```

## Probe a server

`probe` sends a streaming request, stores every raw network chunk and SSE line in JSONL
(base64 plus text), and reports U+FFFD in parsed deltas, U+FFFD bytes (`EF BF BD`) in the raw
stream, and network chunk boundaries that split a UTF-8 character. Secrets are never logged.

The client "omp" uses the OpenAI Responses API (`POST {base}/responses`) with OpenRouter by
default. It uses Chat Completions only when `PI_OPENROUTER_RESPONSES=0`. Probe both with
`--api responses` and `--api chat` (default `chat`).

Local vLLM (key optional; base URL from `OPENAI_BASE_URL`, else `http://localhost:8000/v1`):

```bash
uv run glm-ko-tok probe --target vllm --model <served-model-name> \
  --prompt '안녕하세요를 3번 반복해' --out runs/vllm.jsonl
```

OpenRouter (base URL `https://openrouter.ai/api/v1`, key required in `OPENROUTER_API_KEY`):

```bash
export OPENROUTER_API_KEY=...
uv run glm-ko-tok probe --target openrouter --api responses \
  --model z-ai/glm-5.3 --prompt '안녕하세요를 3번 반복해' \
  --provider <UpstreamName> --out runs/openrouter.jsonl
```

- The model id `z-ai/glm-5.3` is a placeholder. Needs verification on openrouter.ai/models.
- `--provider NAME` (repeatable) pins the upstream provider and disables fallbacks, because
  providers may detokenize differently.
- Optional OpenRouter headers come from `OPENROUTER_REFERER` and `OPENROUTER_TITLE`.
- `--base-url` and `--api-key-env` override the target preset.
- SSE comment lines such as `: OPENROUTER PROCESSING` are recorded as `comment` and ignored.

## Development

```bash
uv run ruff format && uv run ruff check && uv run ty check && uv run pytest --cov
```

Integration tests use the downloaded tokenizers (`tokenizers/<key>/`, or the legacy
`./tokenizer`) and are skipped when files are absent.

## Verify against the reference implementations

`tests/test_reference_hf.py` runs by default. It checks that our ids equal
`tokenizers.Tokenizer.from_file(...).encode(text, add_special_tokens=False).ids` for GLM-5.3
and DeepSeek on all sample lines.

`tests/test_reference_kimi_remote.py` compares our tiktoken backend with Kimi's own
tokenizer. It needs `trust_remote_code=True`, which downloads and runs
`tokenization_kimi.py` (and `encoding_k3.py`) from the Hub. It is excluded from the default
run and skipped unless `RUN_REMOTE_CODE=1`. Read those files first, then run:

```bash
RUN_REMOTE_CODE=1 uv run --group verify pytest -m remote_code
```

The `verify` dependency group holds `transformers`, which `tokenization_kimi.py` imports
(with `tiktoken` and `tokenizers`, already main dependencies). If loading fails with the
newest `transformers`, try an older 4.x release (not verified).
