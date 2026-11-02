"""Hangul syllable coverage of a byte-level BPE vocab."""

import json
from collections import Counter
from dataclasses import dataclass
from typing import Any

from glm_ko_tok.protocols import TokenBackend

HANGUL_START = 0xAC00
HANGUL_END = 0xD7A3


def hangul_syllables() -> list[str]:
    """Return all 11,172 precomposed Hangul syllables."""
    return [chr(c) for c in range(HANGUL_START, HANGUL_END + 1)]


def ksx1001_syllables() -> list[str]:
    """Return the 2,350 KS X 1001 Hangul syllables (EUC-KR rows 0xB0..0xC8)."""
    out = []
    for hi in range(0xB0, 0xC9):
        for lo in range(0xA1, 0xFF):
            ch = bytes([hi, lo]).decode('euc-kr', errors='ignore')
            if len(ch) == 1:
                out.append(ch)
    return out


@dataclass(frozen=True)
class SetCoverage:
    """Coverage numbers for one syllable set."""

    total: int
    single: int
    by_count: dict[int, int]
    in_vocab: int


@dataclass(frozen=True)
class CoverageResult:
    """Coverage for all syllables and for the KS X 1001 subset."""

    all: SetCoverage
    ks: SetCoverage

    @property
    def all_total(self) -> int:
        """Total number of syllables in the full set."""
        return self.all.total

    @property
    def ks_total(self) -> int:
        """Total number of syllables in the KS X 1001 set."""
        return self.ks.total

    @property
    def all_single(self) -> int:
        """Syllables of the full set that encode as one token."""
        return self.all.single

    @property
    def all_by_count(self) -> dict[int, int]:
        """Full-set syllable counts by token count (1, 2, 3, 4 = 4 or more)."""
        return self.all.by_count

    @property
    def all_in_vocab(self) -> int:
        """Full-set syllables that appear inside at least one vocab token."""
        return self.all.in_vocab

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict."""
        return {
            'all': _set_dict(self.all),
            'ks_x_1001': _set_dict(self.ks),
        }

    def to_json(self) -> str:
        """Return the result as a JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    def format(self) -> str:
        """Return a human-readable report."""
        lines = []
        for name, s in (('All Hangul syllables', self.all), ('KS X 1001', self.ks)):
            lines.append(f'{name} ({s.total})')
            lines.append(f'  single token : {s.single} ({s.single / s.total:.1%})')
            for k, label in ((1, '1 token'), (2, '2 tokens'), (3, '3 tokens'), (4, '4+ tokens')):
                lines.append(f'  {label:<13}: {s.by_count.get(k, 0)}')
            lines.append(f'  inside a vocab token: {s.in_vocab} ({s.in_vocab / s.total:.1%})')
        return '\n'.join(lines)


def _set_dict(s: SetCoverage) -> dict[str, Any]:
    return {
        'total': s.total,
        'single_token': s.single,
        'by_token_count': {str(k): v for k, v in sorted(s.by_count.items())},
        'in_vocab_token': s.in_vocab,
    }


def vocab_syllables(backend: TokenBackend) -> set[str]:
    """Collect Hangul syllables found inside any vocab token's decoded bytes."""
    found: set[str] = set()
    for data in backend.iter_vocab_bytes():
        text = data.decode('utf-8', errors='ignore')
        found.update(c for c in text if HANGUL_START <= ord(c) <= HANGUL_END)
    return found


def _coverage(backend: TokenBackend, syllables: list[str], in_vocab: set[str]) -> SetCoverage:
    counts: Counter[int] = Counter()
    for s in syllables:
        n = len(backend.encode(s))
        counts[min(n, 4)] += 1
    return SetCoverage(
        total=len(syllables),
        single=counts[1],
        by_count=dict(counts),
        in_vocab=sum(1 for s in syllables if s in in_vocab),
    )


def compute_coverage(backend: TokenBackend) -> CoverageResult:
    """Compute syllable coverage for a tokenizer.

    Args:
        backend: Tokenizer backend.

    Returns:
        Coverage for all syllables and for KS X 1001.
    """
    in_vocab = vocab_syllables(backend)
    return CoverageResult(
        all=_coverage(backend, hangul_syllables(), in_vocab),
        ks=_coverage(backend, ksx1001_syllables(), in_vocab),
    )
