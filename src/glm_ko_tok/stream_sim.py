"""Simulate token streaming and compare decoding strategies."""

import codecs
import json
from dataclasses import asdict, dataclass

from tokenizers import Tokenizer
from tokenizers.decoders import DecodeStream

from glm_ko_tok.bytes_map import token_bytes
from glm_ko_tok.protocols import TokenizerLike

FFFD = '�'


@dataclass(frozen=True)
class StreamResult:
    """Outcome of one decoding strategy."""

    name: str
    output: str
    fffd_count: int
    equals_truth: bool
    lossy: bool
    skipped: bool = False
    note: str = ''


@dataclass(frozen=True)
class StreamReport:
    """All strategies for one text, plus the true decode."""

    text: str
    truth: str
    results: list[StreamResult]

    def to_json(self) -> str:
        """Return the report as JSON."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)

    def format(self) -> str:
        """Return a human-readable report."""
        lines = [f'truth: {self.truth!r} (U+FFFD={self.truth.count(FFFD)})']
        for r in self.results:
            if r.skipped:
                lines.append(f'{r.name:<14} skipped: {r.note}')
                continue
            lines.append(
                f'{r.name:<14} fffd={r.fffd_count} equals_truth={r.equals_truth} '
                f'lossy={r.lossy} output={r.output!r}'
            )
        return '\n'.join(lines)


def _result(name: str, output: str, truth: str) -> StreamResult:
    fffd = output.count(FFFD)
    return StreamResult(
        name=name,
        output=output,
        fffd_count=fffd,
        equals_truth=output == truth,
        lossy=fffd > truth.count(FFFD),
    )


def _naive(tk: TokenizerLike, ids: list[int]) -> str:
    return ''.join(tk.decode([i]) for i in ids)


def _incremental(tk: TokenizerLike, ids: list[int]) -> str:
    dec = codecs.getincrementaldecoder('utf-8')('replace')
    parts = [dec.decode(token_bytes(tk.id_to_token(i) or '')) for i in ids]
    parts.append(dec.decode(b'', final=True))
    return ''.join(parts)


def _decode_stream(tk: TokenizerLike, ids: list[int]) -> str | None:
    if not isinstance(tk, Tokenizer):
        return None
    stream = DecodeStream(skip_special_tokens=False)
    return ''.join(chunk for i in ids if (chunk := stream.step(tk, i)) is not None)


def simulate_stream(tk: TokenizerLike, text: str) -> StreamReport:
    """Simulate streaming `text` token by token three ways.

    Args:
        tk: Tokenizer.
        text: Text to encode and replay.

    Returns:
        Report comparing naive, incremental, and DecodeStream output to the true decode.
    """
    ids = tk.encode(text, add_special_tokens=False).ids
    truth = tk.decode(ids)
    results = [
        _result('naive', _naive(tk, ids), truth),
        _result('incremental', _incremental(tk, ids), truth),
    ]
    ds = _decode_stream(tk, ids)
    if ds is not None:
        results.append(_result('decode_stream', ds, truth))
    else:
        results.append(
            StreamResult(
                'decode_stream',
                '',
                0,
                equals_truth=False,
                lossy=False,
                skipped=True,
                note='needs a real tokenizers.Tokenizer',
            )
        )
    return StreamReport(text=text, truth=truth, results=results)
