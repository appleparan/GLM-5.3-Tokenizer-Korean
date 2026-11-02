"""Per-token byte split analysis."""

import json
from dataclasses import asdict, dataclass
from itertools import pairwise

from glm_ko_tok.bytes_map import bytes_to_unicode
from glm_ko_tok.coverage import HANGUL_END, HANGUL_START
from glm_ko_tok.protocols import TokenBackend


@dataclass(frozen=True)
class TokenInfo:
    """Facts about one token."""

    id: int
    token: str
    hex: str
    valid_alone: bool
    starts_mid_char: bool
    ends_mid_char: bool
    naive_decode: str


@dataclass(frozen=True)
class Summary:
    """Aggregate numbers for one text."""

    total_tokens: int
    hangul_syllables: int
    tokens_per_syllable: float | None
    invalid_alone: int
    invalid_ratio: float
    split_chars: int


@dataclass(frozen=True)
class Analysis:
    """Token list plus summary."""

    tokens: list[TokenInfo]
    summary: Summary

    def to_json(self) -> str:
        """Return the analysis as a JSON string."""
        return json.dumps(
            {'tokens': [asdict(t) for t in self.tokens], 'summary': asdict(self.summary)},
            ensure_ascii=False,
            indent=2,
        )

    def format(self) -> str:
        """Return a human-readable report."""
        rows = [
            f'{t.id:>8}  {t.token!r:<18} {t.hex:<14} valid={int(t.valid_alone)} '
            f'start_mid={int(t.starts_mid_char)} end_mid={int(t.ends_mid_char)} '
            f'naive={t.naive_decode!r}'
            for t in self.tokens
        ]
        s = self.summary
        tps = 'n/a' if s.tokens_per_syllable is None else f'{s.tokens_per_syllable:.2f}'
        rows.append(
            f'tokens={s.total_tokens} syllables={s.hangul_syllables} tokens/syllable={tps} '
            f'invalid_alone={s.invalid_alone} ({s.invalid_ratio:.1%}) '
            f'split_chars={s.split_chars}'
        )
        return '\n'.join(rows)


def _is_cont(byte: int) -> bool:
    return 0x80 <= byte <= 0xBF


def _valid(data: bytes) -> bool:
    try:
        data.decode('utf-8')
    except UnicodeDecodeError:
        return False
    return True


def analyze_text(backend: TokenBackend, text: str) -> Analysis:
    """Analyze how a text splits into tokens and bytes.

    Args:
        backend: Tokenizer backend.
        text: Text to analyze.

    Returns:
        Per-token info and a summary.
    """
    ids = backend.encode(text)
    table = bytes_to_unicode()
    chunks = [backend.token_bytes(i) for i in ids]
    names = [''.join(table[b] for b in c) for c in chunks]
    full = b''.join(chunks)
    starts = [i for i, b in enumerate(full) if not _is_cont(b)]
    start_set = set(starts)
    owner = [i for i, c in enumerate(chunks) for _ in c]
    infos = []
    pos = 0
    for tid, tok, data in zip(ids, names, chunks, strict=True):
        end = pos + len(data)
        infos.append(
            TokenInfo(
                id=tid,
                token=tok,
                hex=data.hex(),
                valid_alone=_valid(data),
                starts_mid_char=pos not in start_set,
                ends_mid_char=end < len(full) and end not in start_set,
                naive_decode=backend.decode([tid]),
            )
        )
        pos = end
    bounds = [*starts, len(full)]
    split = sum(1 for a, b in pairwise(bounds) if owner[a] != owner[b - 1])
    syl = sum(1 for c in text if HANGUL_START <= ord(c) <= HANGUL_END)
    invalid = sum(1 for t in infos if not t.valid_alone)
    total = len(infos)
    summary = Summary(
        total_tokens=total,
        hangul_syllables=syl,
        tokens_per_syllable=(total / syl) if syl else None,
        invalid_alone=invalid,
        invalid_ratio=(invalid / total) if total else 0.0,
        split_chars=split,
    )
    return Analysis(tokens=infos, summary=summary)
