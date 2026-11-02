"""GPT-2 style ByteLevel table: bytes <-> printable unicode characters."""

from functools import lru_cache


@lru_cache(maxsize=1)
def bytes_to_unicode() -> dict[int, str]:
    """Return the GPT-2 byte to unicode character table.

    Returns:
        Mapping from each byte value (0..255) to a printable character.
    """
    keep = (
        list(range(ord('!'), ord('~') + 1))
        + list(range(ord('\xa1'), ord('\xac') + 1))
        + list(range(ord('\xae'), ord('\xff') + 1))
    )
    codes = list(keep)
    extra = 0
    for b in range(256):
        if b not in keep:
            keep.append(b)
            codes.append(256 + extra)
            extra += 1
    return {b: chr(c) for b, c in zip(keep, codes, strict=True)}


@lru_cache(maxsize=1)
def unicode_to_bytes() -> dict[str, int]:
    """Return the inverse of `bytes_to_unicode`.

    Returns:
        Mapping from table character to byte value.
    """
    return {ch: b for b, ch in bytes_to_unicode().items()}


def token_bytes(token: str) -> bytes:
    """Convert a byte-level token string to the raw bytes it stands for.

    Args:
        token: Token string as stored in the vocab (ByteLevel alphabet).

    Returns:
        The raw bytes.

    Raises:
        ValueError: If a character is not in the ByteLevel alphabet.
    """
    inv = unicode_to_bytes()
    try:
        return bytes(inv[ch] for ch in token)
    except KeyError as e:
        msg = f'not a byte-level token: {token!r}'
        raise ValueError(msg) from e
