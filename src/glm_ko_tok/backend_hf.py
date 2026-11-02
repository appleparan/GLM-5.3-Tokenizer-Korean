"""Backend for `tokenizers.Tokenizer` (tokenizer.json) models."""

from collections.abc import Iterator

from tokenizers import Tokenizer

from glm_ko_tok.bytes_map import token_bytes


class HFBackend:
    """Wrap a `tokenizers.Tokenizer` that uses the GPT-2 ByteLevel alphabet."""

    def __init__(self, tokenizer: Tokenizer) -> None:
        """Wrap a loaded tokenizer.

        Args:
            tokenizer: The `tokenizers` object.
        """
        self._tk = tokenizer

    @property
    def tokenizer(self) -> Tokenizer:
        """The wrapped tokenizer (used for `DecodeStream`)."""
        return self._tk

    @property
    def vocab_size(self) -> int:
        """Number of tokens including added tokens."""
        return self._tk.get_vocab_size(with_added_tokens=True)

    def encode(self, text: str) -> list[int]:
        """Encode text without special tokens."""
        return self._tk.encode(text, add_special_tokens=False).ids

    def token_bytes(self, token_id: int) -> bytes:
        """Return the raw bytes of a token; non byte-level tokens fall back to UTF-8."""
        token = self._tk.id_to_token(token_id)
        if token is None:
            msg = f'unknown token id: {token_id}'
            raise KeyError(msg)
        try:
            return token_bytes(token)
        except ValueError:
            return token.encode('utf-8')

    def decode(self, ids: list[int]) -> str:
        """Decode ids to text."""
        return self._tk.decode(ids)

    def iter_vocab_bytes(self) -> Iterator[bytes]:
        """Yield bytes of every vocab token written in the ByteLevel alphabet."""
        for token in self._tk.get_vocab():
            try:
                yield token_bytes(token)
            except ValueError:
                continue
