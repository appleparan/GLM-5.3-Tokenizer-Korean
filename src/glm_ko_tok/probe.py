"""Probe an OpenAI-compatible streaming endpoint and record the raw SSE bytes."""

import codecs
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

from glm_ko_tok.probe_config import (
    ProbeConfig,
    ProbeConfigError,
    build_config,
)
from glm_ko_tok.probe_sse import SseCollector, _b64

__all__ = [
    'ProbeConfig',
    'ProbeConfigError',
    'ProbeError',
    'ProbeResult',
    'build_config',
    'run_probe',
]

logger = logging.getLogger(__name__)

FFFD = '�'
FFFD_BYTES = b'\xef\xbf\xbd'
TIMEOUT = httpx.Timeout(connect=10.0, read=120.0, write=10.0, pool=10.0)
SECRET_HEADER_PARTS = ('auth', 'key', 'token', 'cookie', 'secret')


class ProbeError(RuntimeError):
    """Raised when the server answers with an HTTP error."""


@dataclass(frozen=True)
class ProbeResult:
    """Summary of one probe run."""

    chunks: int
    lines: int
    comments: int
    data_events: int
    deltas: int
    text: str
    fffd_in_deltas: int
    fffd_in_raw: int
    boundary_splits: int
    bad_json: int
    errors: tuple[str, ...]
    done: bool

    def format(self) -> str:
        """Return a human-readable report."""
        lines = [
            f'chunks (network)        : {self.chunks}',
            f'lines / comments        : {self.lines} / {self.comments}',
            f'data events / deltas    : {self.data_events} / {self.deltas}',
            f'U+FFFD in deltas        : {self.fffd_in_deltas}',
            f'U+FFFD in raw (EF BF BD): {self.fffd_in_raw}',
            f'chunk boundaries splitting a UTF-8 char: {self.boundary_splits}',
            f'finished cleanly        : {self.done}',
        ]
        if self.bad_json:
            lines.append(f'unparsable data lines   : {self.bad_json}')
        lines.extend(f'server error            : {e}' for e in self.errors)
        lines.append(f'text: {self.text!r}')
        return '\n'.join(lines)


def _safe_headers(headers: httpx.Headers) -> dict[str, str]:
    return {
        k: v for k, v in headers.items() if not any(p in k.lower() for p in SECRET_HEADER_PARTS)
    }


def _stream(
    response: httpx.Response, collector: SseCollector
) -> tuple[list[dict[str, Any]], int, int]:
    """Read raw chunks; return chunk records, raw FFFD count, boundary splits."""
    decoder = codecs.getincrementaldecoder('utf-8')('replace')
    chunk_records: list[dict[str, Any]] = []
    raw = bytearray()
    splits = 0
    for index, chunk in enumerate(response.iter_raw(), 1):
        decoder.decode(chunk)
        splits_char = bool(decoder.getstate()[0])
        splits += int(splits_char)
        raw.extend(chunk)
        chunk_records.append(
            {
                'kind': 'chunk',
                'index': index,
                'size': len(chunk),
                'b64': _b64(chunk),
                'splits_char': splits_char,
            }
        )
        collector.feed(chunk)
    collector.finish()
    return chunk_records, bytes(raw).count(FFFD_BYTES), splits


def _write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        f.writelines(json.dumps(r, ensure_ascii=False) + '\n' for r in records)


def run_probe(
    config: ProbeConfig,
    out: Path | str | None = None,
    transport: httpx.BaseTransport | None = None,
) -> ProbeResult:
    """Send a streaming request and analyze the raw bytes.

    Args:
        config: Resolved probe config.
        out: Optional JSONL output path.
        transport: Optional httpx transport (tests).

    Returns:
        Summary of the run.

    Raises:
        ProbeError: On HTTP error status or connection failure.
    """
    collector = SseCollector(api=config.api)
    logger.info('POST %s', config.url)
    try:
        with (
            httpx.Client(timeout=TIMEOUT, transport=transport) as client,
            client.stream(
                'POST', config.url, json=config.body(), headers=config.headers()
            ) as response,
        ):
            if response.status_code >= 400:
                body = response.read().decode('utf-8', errors='replace')[:500]
                msg = f'HTTP {response.status_code} from {config.url}: {body}'
                raise ProbeError(msg)
            chunk_records, raw_fffd, splits = _stream(response, collector)
            status = response.status_code
            resp_headers = _safe_headers(response.headers)
    except httpx.HTTPError as e:
        msg = f'request to {config.url} failed: {type(e).__name__}: {e}'
        raise ProbeError(msg) from e
    text = ''.join(collector.deltas)
    result = ProbeResult(
        chunks=len(chunk_records),
        lines=collector.lines,
        comments=collector.comments,
        data_events=collector.data_events,
        deltas=len(collector.deltas),
        text=text,
        fffd_in_deltas=text.count(FFFD),
        fffd_in_raw=raw_fffd,
        boundary_splits=splits,
        bad_json=collector.bad_json,
        errors=tuple(collector.errors),
        done=collector.done,
    )
    if out is not None:
        header = {
            'kind': 'header',
            'target': config.target,
            'api': config.api,
            'base_url': config.base_url,
            'model': config.model,
            'status': status,
            'request': config.body(),
            'response_headers': resp_headers,
        }
        summary = {'kind': 'summary', **{k: v for k, v in result.__dict__.items() if k != 'text'}}
        summary['errors'] = list(result.errors)
        _write_jsonl(Path(out), [header, *chunk_records, *collector.records, summary])
    return result


def default_env() -> dict[str, str]:
    """Return a copy of the process environment."""
    return dict(os.environ)
