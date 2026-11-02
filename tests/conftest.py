"""Shared fixtures: a fake byte-level backend and the optional real tokenizers."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from glm_ko_tok.loader import (
    DEFAULT_ROOT,
    LEGACY_DIR,
    LoadedModel,
    TokenizerNotFoundError,
    load_model,
)
from glm_ko_tok.sample_stats import read_parallel_pairs
from glm_ko_tok.textio import read_cases

ROOT = Path(__file__).resolve().parent.parent
SAMPLES = ROOT / 'samples'


class FakeTokenizer:
    """Greedy longest-match byte-level backend with a configurable vocab."""

    def __init__(self, extra: list[bytes]) -> None:
        self._pieces = [bytes([b]) for b in range(256)] + list(extra)
        self._ids = {p: i for i, p in enumerate(self._pieces)}
        self._max = max(len(p) for p in self._pieces)

    @property
    def vocab_size(self) -> int:
        return len(self._pieces)

    def encode(self, text: str) -> list[int]:
        data = text.encode('utf-8')
        ids: list[int] = []
        pos = 0
        while pos < len(data):
            for size in range(min(self._max, len(data) - pos), 0, -1):
                piece = data[pos : pos + size]
                if piece in self._ids:
                    ids.append(self._ids[piece])
                    pos += size
                    break
        return ids

    def token_bytes(self, token_id: int) -> bytes:
        return self._pieces[token_id]

    def decode(self, ids: list[int]) -> str:
        return b''.join(self._pieces[i] for i in ids).decode('utf-8', errors='replace')

    def iter_vocab_bytes(self) -> Iterator[bytes]:
        yield from self._pieces


@pytest.fixture
def fake_tk() -> FakeTokenizer:
    """Fake backend where 한 is split 1+2 bytes and 국 is a single token."""
    return FakeTokenizer(['국'.encode(), b'\x95\x9c', b'ab'])


@pytest.fixture(scope='session')
def load_real():
    """Return a loader for a real downloaded model; the test is skipped when files are absent."""

    def _load(key: str) -> LoadedModel:
        try:
            return load_model(key, ROOT / DEFAULT_ROOT, ROOT / LEGACY_DIR)
        except TokenizerNotFoundError:
            pytest.skip(f'{key} tokenizer not downloaded')

    return _load


@pytest.fixture(scope='session')
def sample_lines() -> list[str]:
    """Every line of samples/korean.txt and both sides of samples/parallel_ko_zh.txt."""
    lines = read_cases(SAMPLES / 'korean.txt')
    for ko, zh in read_parallel_pairs(SAMPLES / 'parallel_ko_zh.txt'):
        lines.extend([ko, zh])
    return lines


@pytest.fixture(scope='session')
def real_tk(load_real):
    """Real GLM-5.3 backend, or skip when not downloaded."""
    return load_real('glm-5.3').backend
