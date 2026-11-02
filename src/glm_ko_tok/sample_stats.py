"""Token cost of the sample sentences: Korean lines and ko/zh parallel pairs."""

from dataclasses import dataclass
from pathlib import Path

from glm_ko_tok.protocols import TokenBackend
from glm_ko_tok.textio import read_cases

FFFD = '�'


class SampleFormatError(ValueError):
    """Raised when a sample file has a malformed line."""


@dataclass(frozen=True)
class KoreanStats:
    """Totals over the lines of the Korean sample file."""

    lines: int
    total_tokens: int
    chars: int
    tokens_per_char: float
    naive_fffd: int


@dataclass(frozen=True)
class PairStats:
    """Token counts for one ko/zh pair."""

    ko: str
    zh: str
    ko_tokens: int
    ko_chars: int
    zh_tokens: int
    zh_chars: int


@dataclass(frozen=True)
class ParallelStats:
    """Totals over all ko/zh pairs, plus the per pair numbers."""

    pairs: int
    ko_tokens: int
    ko_chars: int
    zh_tokens: int
    zh_chars: int
    ko_tokens_per_char: float
    zh_tokens_per_char: float
    per_pair: list[PairStats]


def _chars(text: str) -> int:
    """Count characters that are not whitespace."""
    return sum(1 for c in text if not c.isspace())


def _ratio(tokens: int, chars: int) -> float:
    return tokens / chars if chars else 0.0


def korean_stats(backend: TokenBackend, lines: list[str]) -> KoreanStats:
    """Count tokens, characters and naive-decode U+FFFD over Korean sample lines.

    Args:
        backend: Tokenizer backend.
        lines: One sample per item.

    Returns:
        Totals. Naive decoding decodes every token alone.
    """
    tokens = chars = fffd = 0
    for line in lines:
        ids = backend.encode(line)
        tokens += len(ids)
        chars += _chars(line)
        fffd += ''.join(backend.decode([i]) for i in ids).count(FFFD)
    return KoreanStats(len(lines), tokens, chars, _ratio(tokens, chars), fffd)


def read_parallel_pairs(path: Path | str) -> list[tuple[str, str]]:
    """Read `ko<TAB>zh` lines; blank and `#` lines are skipped.

    Args:
        path: File path (UTF-8).

    Returns:
        List of (ko, zh) pairs.

    Raises:
        SampleFormatError: If a line does not have exactly two tab separated fields.
    """
    pairs = []
    for n, line in enumerate(read_cases(path), 1):
        fields = line.split('\t')
        if len(fields) != 2 or not all(f.strip() for f in fields):
            msg = f'{path}: case {n} must be "ko<TAB>zh": {line!r}'
            raise SampleFormatError(msg)
        pairs.append((fields[0], fields[1]))
    return pairs


def parallel_stats(backend: TokenBackend, pairs: list[tuple[str, str]]) -> ParallelStats:
    """Count tokens per character for Korean and Chinese versions of the same sentences.

    Args:
        backend: Tokenizer backend.
        pairs: (ko, zh) sentence pairs.

    Returns:
        Totals and per pair numbers.
    """
    per_pair = [
        PairStats(ko, zh, len(backend.encode(ko)), _chars(ko), len(backend.encode(zh)), _chars(zh))
        for ko, zh in pairs
    ]
    ko_t = sum(p.ko_tokens for p in per_pair)
    ko_c = sum(p.ko_chars for p in per_pair)
    zh_t = sum(p.zh_tokens for p in per_pair)
    zh_c = sum(p.zh_chars for p in per_pair)
    return ParallelStats(
        len(pairs), ko_t, ko_c, zh_t, zh_c, _ratio(ko_t, ko_c), _ratio(zh_t, zh_c), per_pair
    )
