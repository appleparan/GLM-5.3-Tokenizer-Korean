"""Shared fixtures: a fake byte-level tokenizer and the optional real tokenizer."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from glm_ko_tok.bytes_map import bytes_to_unicode

REAL_DIR = Path(__file__).resolve().parent.parent / 'tokenizer'


class FakeTokenizer:
    """Greedy longest-match byte-level tokenizer with a configurable vocab."""

    def __init__(self, extra: list[bytes]) -> None:
        table = bytes_to_unicode()
        pieces = [bytes([b]) for b in range(256)] + list(extra)
        self._pieces = pieces
        self._ids = {p: i for i, p in enumerate(pieces)}
        self._table = table
        self._max = max(len(p) for p in pieces)

    def _to_str(self, piece: bytes) -> str:
        return ''.join(self._table[b] for b in piece)

    def encode(self, sequence: str, *, add_special_tokens: bool = False) -> SimpleNamespace:
        data = sequence.encode('utf-8')
        ids: list[int] = []
        pos = 0
        while pos < len(data):
            for size in range(min(self._max, len(data) - pos), 0, -1):
                piece = data[pos : pos + size]
                if piece in self._ids:
                    ids.append(self._ids[piece])
                    pos += size
                    break
        return SimpleNamespace(ids=ids, tokens=[self.id_to_token(i) for i in ids])

    def id_to_token(self, token_id: int) -> str:
        return self._to_str(self._pieces[token_id])

    def decode(self, ids: list[int], skip_special_tokens: bool = False) -> str:
        return b''.join(self._pieces[i] for i in ids).decode('utf-8', errors='replace')

    def get_vocab(self) -> dict[str, int]:
        return {self._to_str(p): i for p, i in self._ids.items()}


@pytest.fixture
def fake_tk() -> FakeTokenizer:
    """Fake tokenizer where 한 is split 1+2 bytes and 국 is a single token."""
    return FakeTokenizer(['국'.encode(), b'\xed', b'\x95\x9c', b'ab'])


@pytest.fixture(scope='session')
def real_tk():
    """Real GLM-5.3 tokenizer, or skip when not downloaded."""
    if not (REAL_DIR / 'tokenizer.json').exists():
        pytest.skip('real tokenizer not downloaded')
    from glm_ko_tok.loader import load_tokenizer

    return load_tokenizer(REAL_DIR)
