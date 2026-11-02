"""Pre-tokenizer summary: which regex patterns split text, and do they know Han or Hangul."""

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from glm_ko_tok.backend_tiktoken import KIMI_PAT_STR

HAN_RANGES = (
    (0x2E80, 0x2FDF),
    (0x3400, 0x4DBF),
    (0x4E00, 0x9FFF),
    (0xF900, 0xFAFF),
    (0x20000, 0x2FA1F),
)
HANGUL_RANGES = (
    (0x1100, 0x11FF),
    (0x3130, 0x318F),
    (0xA960, 0xA97F),
    (0xAC00, 0xD7FF),
)
_HAN_CLASS = re.compile(r'\\p\{(?:(?:Script|sc|Script_Extensions|scx)=)?(?:Han|Hani)\}', re.I)
_HANGUL_CLASS = re.compile(r'\\p\{(?:(?:Script|sc|Script_Extensions|scx)=)?(?:Hangul|Hang)\}', re.I)
# A code point written as an escape or as a literal non-ASCII character.
_ATOM = re.compile(r'\\u([0-9a-fA-F]{4})|\\x\{([0-9a-fA-F]+)\}|\\U([0-9a-fA-F]{8})|([^\x00-\x7f])')


@dataclass(frozen=True)
class PreTokenizerInfo:
    """Regex patterns of a pre-tokenizer and what they say about CJK scripts."""

    patterns: list[str]
    explicit_han: bool
    explicit_hangul: bool


def _atom_code(m: re.Match[str]) -> int:
    if m.group(4):
        return ord(m.group(4))
    return int(m.group(1) or m.group(2) or m.group(3), 16)


def _code_intervals(pattern: str) -> list[tuple[int, int]]:
    """Return code points and `a-b` ranges written explicitly in a pattern."""
    atoms = list(_ATOM.finditer(pattern))
    out: list[tuple[int, int]] = []
    i = 0
    while i < len(atoms):
        code = _atom_code(atoms[i])
        nxt = atoms[i + 1] if i + 1 < len(atoms) else None
        if nxt is not None and pattern[atoms[i].end() : nxt.start()] == '-':
            other = _atom_code(nxt)
            out.append((min(code, other), max(code, other)))
            i += 2
        else:
            out.append((code, code))
            i += 1
    return out


def _overlaps(intervals: list[tuple[int, int]], ranges: tuple[tuple[int, int], ...]) -> bool:
    return any(a <= rb and lo <= b for a, b in intervals for lo, rb in ranges)


def analyze_patterns(patterns: list[str]) -> PreTokenizerInfo:
    r"""Check patterns for an explicit Han or Hangul class or code point range.

    `\p{L}` and similar general classes do not count as explicit.

    Args:
        patterns: Regex patterns.

    Returns:
        The patterns plus two flags.
    """
    han = hangul = False
    for pat in patterns:
        intervals = _code_intervals(pat)
        han = han or bool(_HAN_CLASS.search(pat)) or _overlaps(intervals, HAN_RANGES)
        hangul = hangul or bool(_HANGUL_CLASS.search(pat)) or _overlaps(intervals, HANGUL_RANGES)
    return PreTokenizerInfo(list(patterns), han, hangul)


def _collect(node: Any, out: list[str]) -> None:  # noqa: ANN401
    if not isinstance(node, dict):
        return
    regex = (node.get('pattern') or {}).get('Regex')
    if isinstance(regex, str):
        out.append(regex)
    for child in node.get('pretokenizers') or []:
        _collect(child, out)


def hf_patterns(tokenizer_json: Path | str) -> list[str]:
    """Return the regex patterns in `pre_tokenizer` of a tokenizer.json, in order.

    Args:
        tokenizer_json: Path of the file.

    Returns:
        The patterns (empty if there is no pre-tokenizer).
    """
    data = json.loads(Path(tokenizer_json).read_text(encoding='utf-8'))
    out: list[str] = []
    _collect(data.get('pre_tokenizer'), out)
    return out


def pretokenizer_info(kind: str, directory: Path) -> PreTokenizerInfo | None:
    """Summarize a model's pre-tokenizer.

    Args:
        kind: Backend kind, `hf` or `tiktoken`.
        directory: Directory with the model files.

    Returns:
        The summary, or None if tokenizer.json is missing for an HF model.
    """
    if kind == 'tiktoken':
        return analyze_patterns([KIMI_PAT_STR])
    path = directory / 'tokenizer.json'
    if not path.is_file():
        return None
    return analyze_patterns(hf_patterns(path))
