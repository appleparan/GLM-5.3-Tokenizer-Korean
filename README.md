# GLM-5.3-Tokenizer-Korean

CLI to find out why Korean text shows broken characters (U+FFFD) when streaming from GLM-5.3.
GLM-5.3 uses a byte-level BPE tokenizer. Most Hangul syllables are 3 UTF-8 bytes and are
split across several tokens. A client that decodes each token alone prints U+FFFD.

## Install

```bash
uv sync
uv run glm-ko-tok fetch            # downloads tokenizer.json and tokenizer_config.json to ./tokenizer
```

## Commands

| Command | Purpose |
|---------|---------|
| `fetch [--repo R] [--dir D]` | Download only the two tokenizer files |
| `coverage [--json]` | Hangul syllables that are 1/2/3/4+ tokens, and inside vocab tokens |
| `compare [--json]` | Token cost of Hangul, Hanja, GB2312, CJK, jamo; vocab composition |
| `analyze TEXT` or `--file F [--per-line] [--json]` | Per-token bytes, validity, split characters |
| `stream-sim TEXT` or `--file F [--per-line] [--json]` | Naive vs incremental vs `DecodeStream` decoding |
| `probe ...` | Capture a real streaming response and check for U+FFFD |

Sample inputs: `samples/korean.txt` (`#` lines are comments). Example:

```bash
uv run glm-ko-tok analyze '안녕하세요'
uv run glm-ko-tok stream-sim --file samples/korean.txt --per-line
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

Integration tests use `./tokenizer` and are skipped when it is absent.
