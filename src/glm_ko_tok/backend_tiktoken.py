"""Backend for tiktoken based models (Kimi-K3).

Special tokens are not needed for this analysis, so the Kimi encoding is built with none.
"""

from collections.abc import Iterator
from pathlib import Path

import tiktoken
import tiktoken.load

# Copied verbatim from tokenization_kimi.py at the pinned revision:
# https://huggingface.co/moonshotai/Kimi-K3/blob/f831ab66814297da540d832a5235f8e904f29d06/tokenization_kimi.py
KIMI_PAT_STR = '|'.join(
    [
        r"""[\p{Han}]+""",
        r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]*[\p{Ll}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]+(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
        r"""[^\r\n\p{L}\p{N}]?[\p{Lu}\p{Lt}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]+[\p{Ll}\p{Lm}\p{Lo}\p{M}&&[^\p{Han}]]*(?i:'s|'t|'re|'ve|'m|'ll|'d)?""",
        r"""\p{N}{1,3}""",
        r""" ?[^\s\p{L}\p{N}]+[\r\n]*""",
        r"""\s*[\r\n]+""",
        r"""\s+(?!\S)""",
        r"""\s+""",
    ]
)


class TiktokenBackend:
    """Wrap a `tiktoken.Encoding`."""

    def __init__(self, encoding: tiktoken.Encoding) -> None:
        """Wrap an encoding.

        Args:
            encoding: The tiktoken encoding.
        """
        self._enc = encoding

    @property
    def vocab_size(self) -> int:
        """Number of token ids (highest rank + 1, plus special tokens)."""
        return self._enc.n_vocab

    def encode(self, text: str) -> list[int]:
        """Encode text; special-token text is treated as plain text."""
        return self._enc.encode(text, disallowed_special=())

    def token_bytes(self, token_id: int) -> bytes:
        """Return the raw bytes of a token."""
        return self._enc.decode_single_token_bytes(token_id)

    def decode(self, ids: list[int]) -> str:
        """Decode ids; invalid UTF-8 becomes U+FFFD."""
        return self._enc.decode(ids, errors='replace')

    def iter_vocab_bytes(self) -> Iterator[bytes]:
        """Yield bytes of every vocab token."""
        yield from self._enc.token_byte_values()


def build_kimi_encoding(model_path: Path | str) -> TiktokenBackend:
    """Build the Kimi-K3 encoding from `tiktoken.model` (no special tokens).

    Args:
        model_path: Path of the base64 token and rank file.

    Returns:
        The backend.
    """
    ranks = tiktoken.load.load_tiktoken_bpe(str(model_path))
    enc = tiktoken.Encoding(
        name='kimi-k3', pat_str=KIMI_PAT_STR, mergeable_ranks=ranks, special_tokens={}
    )
    return TiktokenBackend(enc)
