"""Structural types for the tokenizer backends."""

from collections.abc import Iterator
from typing import Protocol


class TokenBackend(Protocol):
    """The small tokenizer API every analysis needs.

    Encoding never adds special tokens. Special tokens are not part of this analysis.
    """

    @property
    def vocab_size(self) -> int:
        """Number of tokens in the vocab."""
        ...

    def encode(self, text: str) -> list[int]:
        """Encode text to token ids."""
        ...

    def token_bytes(self, token_id: int) -> bytes:
        """Return the raw bytes a token id stands for."""
        ...

    def decode(self, ids: list[int]) -> str:
        """Decode ids to text; invalid UTF-8 becomes U+FFFD."""
        ...

    def iter_vocab_bytes(self) -> Iterator[bytes]:
        """Yield the raw bytes of every byte-level vocab token."""
        ...
