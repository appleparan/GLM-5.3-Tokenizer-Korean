"""Compare token cost of Hangul, Hanja, and Chinese character sets."""

import json
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from glm_ko_tok.coverage import HANGUL_END, HANGUL_START, hangul_syllables, ksx1001_syllables
from glm_ko_tok.protocols import TokenBackend


def _legacy_set(codec: str, leads: range, trails: range = range(0xA1, 0xFF)) -> list[str]:
    out = []
    for hi in leads:
        for lo in trails:
            ch = bytes([hi, lo]).decode(codec, errors='ignore')
            if len(ch) == 1:
                out.append(ch)
    return out


def char_sets() -> dict[str, list[str]]:
    """Return the named character sets to compare (ordered)."""
    return {
        'Hangul KS X 1001': ksx1001_syllables(),
        'Hangul all': hangul_syllables(),
        'Chinese GB2312 L1': _legacy_set('gb2312', range(0xB0, 0xD8)),
        'Hanja KS X 1001': _legacy_set('euc-kr', range(0xCA, 0xFE)),
        'CJK Unified': [chr(c) for c in range(0x4E00, 0x9FFF + 1)],
        'Hangul Compat Jamo': [chr(c) for c in range(0x3131, 0x3163 + 1)],
    }


@dataclass(frozen=True)
class SetStats:
    """Token counts for one character set."""

    name: str
    total: int
    by_count: dict[int, int]
    one_token_ratio: float


@dataclass(frozen=True)
class VocabStats:
    """Composition of the vocab."""

    vocab_size: int
    with_hangul: int
    with_han: int
    invalid_alone: int


@dataclass(frozen=True)
class ModelCompare:
    """Comparison for one model."""

    key: str
    sets: list[SetStats]
    vocab: VocabStats

    def format(self) -> str:
        """Return a table."""
        head = (
            f'{"set":<20} {"total":>6} {"1 tok":>6} {"2 tok":>6} {"3 tok":>6} {"4+":>5} '
            f'{"1-tok %":>8}'
        )
        lines = [head]
        lines.extend(
            f'{s.name:<20} {s.total:>6} {s.by_count[1]:>6} {s.by_count[2]:>6} '
            f'{s.by_count[3]:>6} {s.by_count[4]:>5} {s.one_token_ratio:>8.1%}'
            for s in self.sets
        )
        v = self.vocab
        lines.append('')
        lines.append(
            f'vocab size: {v.vocab_size}; tokens with Hangul syllable: {v.with_hangul}; '
            f'with CJK ideograph: {v.with_han}; invalid UTF-8 alone: {v.invalid_alone}'
        )
        return '\n'.join(lines)


@dataclass(frozen=True)
class CompareResult:
    """Comparison across one or more models."""

    models: list[ModelCompare]

    def to_json(self) -> str:
        """Return the result as JSON, keyed by model."""
        data: dict[str, Any] = {m.key: asdict(m) for m in self.models}
        return json.dumps(data, ensure_ascii=False, indent=2)

    def summary_table(self) -> str:
        """Return one row per character set, one column per model, cell = 1-token %."""
        width = max(10, *(len(m.key) for m in self.models))
        head = f'{"set":<20} ' + ' '.join(f'{m.key:>{width}}' for m in self.models)
        lines = [head]
        for i, row in enumerate(self.models[0].sets):
            cells = ' '.join(f'{m.sets[i].one_token_ratio:>{width}.1%}' for m in self.models)
            lines.append(f'{row.name:<20} {cells}')
        return '\n'.join(lines)

    def format(self) -> str:
        """Return a table per model, plus a summary table when there are several models."""
        if len(self.models) == 1:
            return self.models[0].format()
        parts = [f'== {m.key} ==\n{m.format()}' for m in self.models]
        parts.append(f'== summary: 1-token % ==\n{self.summary_table()}')
        return '\n\n'.join(parts)


def _stats(backend: TokenBackend, name: str, chars: list[str]) -> SetStats:
    counts: Counter[int] = Counter()
    for c in chars:
        counts[min(len(backend.encode(c)), 4)] += 1
    by_count = {k: counts[k] for k in (1, 2, 3, 4)}
    return SetStats(name, len(chars), by_count, by_count[1] / len(chars))


def vocab_composition(backend: TokenBackend) -> VocabStats:
    """Count vocab tokens containing Hangul, CJK ideographs, or invalid bytes alone."""
    hangul = han = invalid = 0
    for data in backend.iter_vocab_bytes():
        text = data.decode('utf-8', errors='ignore')
        hangul += any(HANGUL_START <= ord(c) <= HANGUL_END for c in text)
        han += any(0x4E00 <= ord(c) <= 0x9FFF for c in text)
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            invalid += 1
    return VocabStats(backend.vocab_size, hangul, han, invalid)


def compare_backend(key: str, backend: TokenBackend) -> ModelCompare:
    """Compare token cost across character sets for one model.

    Args:
        key: Model key.
        backend: Tokenizer backend.

    Returns:
        Per-set stats and vocab composition.
    """
    sets = [_stats(backend, name, chars) for name, chars in char_sets().items()]
    return ModelCompare(key=key, sets=sets, vocab=vocab_composition(backend))
