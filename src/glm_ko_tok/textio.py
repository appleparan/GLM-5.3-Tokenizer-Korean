"""Input and output helpers shared by CLI commands."""

import sys
from pathlib import Path


def write(text: str) -> None:
    """Write a line to stdout (single CLI output point)."""
    sys.stdout.write(text + '\n')


def write_err(text: str) -> None:
    """Write a line to stderr."""
    sys.stderr.write(text + '\n')


def read_cases(path: Path | str) -> list[str]:
    """Read a sample file: one case per line; skip blank and `#` comment lines.

    Args:
        path: File path (UTF-8).

    Returns:
        The case lines.
    """
    lines = Path(path).read_text(encoding='utf-8').splitlines()
    return [ln for ln in lines if ln.strip() and not ln.startswith('#')]


def shorten(text: str, width: int = 24) -> str:
    """Shorten a text for a table cell."""
    text = text.replace('\n', '\\n')
    return text if len(text) <= width else text[: width - 1] + '…'
