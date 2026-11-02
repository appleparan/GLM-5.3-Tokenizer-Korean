"""Structural types for the tokenizer API subset we use."""

from typing import Protocol


class EncodingLike(Protocol):
    """Result of `encode`."""

    @property
    def ids(self) -> list[int]:
        """Token ids."""
        ...

    @property
    def tokens(self) -> list[str]:
        """Token strings (ByteLevel alphabet)."""
        ...


class TokenizerLike(Protocol):
    """Subset of `tokenizers.Tokenizer` used here."""

    def encode(self, sequence: str, *, add_special_tokens: bool = True) -> EncodingLike:
        """Encode text."""
        ...

    def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
        """Decode ids."""
        ...

    def id_to_token(self, id: int) -> str | None:
        """Return the token string for an id."""
        ...

    def get_vocab(self, with_added_tokens: bool = True) -> dict[str, int]:
        """Return the vocab."""
        ...
