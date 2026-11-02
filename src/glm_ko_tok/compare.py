"""Compare token cost of Hangul, Hanja, and Chinese character sets."""

import json
from collections import Counter
from dataclasses import asdict, dataclass
from typing import Any

from glm_ko_tok.bytes_map import token_bytes
from glm_ko_tok.coverage import HANGUL_END, HANGUL_START, hangul_syllables, ksx1001_syllables
from glm_ko_tok.protocols import TokenizerLike


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

    with_hangul: int
    with_han: int
    invalid_alone: int


@dataclass(frozen=True)
class CompareResult:
    """Full comparison."""

    sets: list[SetStats]
    vocab: VocabStats

    def to_json(self) -> str:
        """Return the result as JSON."""
        data: dict[str, Any] = asdict(self)
        return json.dumps(data, ensure_ascii=False, indent=2)

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
            f'vocab tokens with Hangul syllable: {v.with_hangul}; with CJK ideograph: '
            f'{v.with_han}; invalid UTF-8 alone: {v.invalid_alone}'
        )
        return '\n'.join(lines)


def _stats(tk: TokenizerLike, name: str, chars: list[str]) -> SetStats:
    counts: Counter[int] = Counter()
    for c in chars:
        counts[min(len(tk.encode(c, add_special_tokens=False).ids), 4)] += 1
    by_count = {k: counts[k] for k in (1, 2, 3, 4)}
    return SetStats(name, len(chars), by_count, by_count[1] / len(chars))


def vocab_composition(tk: TokenizerLike) -> VocabStats:
    """Count vocab tokens containing Hangul, CJK ideographs, or invalid bytes alone."""
    hangul = han = invalid = 0
    for token in tk.get_vocab():
        try:
            data = token_bytes(token)
        except ValueError:
            continue
        text = data.decode('utf-8', errors='ignore')
        hangul += any(HANGUL_START <= ord(c) <= HANGUL_END for c in text)
        han += any(0x4E00 <= ord(c) <= 0x9FFF for c in text)
        try:
            data.decode('utf-8')
        except UnicodeDecodeError:
            invalid += 1
    return VocabStats(hangul, han, invalid)


def compare_tokenizer(tk: TokenizerLike) -> CompareResult:
    """Compare token cost across character sets.

    Args:
        tk: Tokenizer.

    Returns:
        Per-set stats and vocab composition.
    """
    sets = [_stats(tk, name, chars) for name, chars in char_sets().items()]
    return CompareResult(sets=sets, vocab=vocab_composition(tk))
