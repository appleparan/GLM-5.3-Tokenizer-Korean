"""Incremental SSE parser that records raw lines and extracts text deltas."""

import base64
import json
from dataclasses import dataclass, field
from typing import Any

RESPONSES_DELTA = 'response.output_text.delta'
RESPONSES_DONE = 'response.completed'
RESPONSES_ERRORS = ('response.failed', 'error')


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


@dataclass
class SseCollector:
    """Feed raw network chunks; collects records, deltas, and counters."""

    api: str
    records: list[dict[str, Any]] = field(default_factory=list)
    deltas: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    lines: int = 0
    comments: int = 0
    data_events: int = 0
    bad_json: int = 0
    done: bool = False
    _event: str | None = None
    _buf: bytearray = field(default_factory=bytearray)

    def feed(self, chunk: bytes) -> None:
        """Add a raw network chunk and process complete lines."""
        self._buf.extend(chunk)
        while (i := self._buf.find(b'\n')) >= 0:
            line = bytes(self._buf[:i])
            del self._buf[: i + 1]
            self._line(line)

    def finish(self) -> None:
        """Process a final line that has no trailing newline."""
        if self._buf:
            self._line(bytes(self._buf))
            self._buf.clear()

    def _line(self, raw: bytes) -> None:
        self.lines += 1
        raw = raw.removesuffix(b'\r')
        text = raw.decode('utf-8', errors='replace')
        kind = 'comment' if raw.startswith(b':') else 'line'
        self.records.append({'kind': kind, 'index': self.lines, 'raw_b64': _b64(raw), 'text': text})
        if kind == 'comment':
            self.comments += 1
        elif not text:
            self._event = None
        elif text.startswith('event:'):
            self._event = text[6:].strip()
        elif text.startswith('data:'):
            self._data(text[5:].removeprefix(' '))

    def _data(self, payload: str) -> None:
        if payload.strip() == '[DONE]':
            self.done = True
            self.records.append({'kind': 'done'})
            return
        try:
            obj = json.loads(payload)
        except json.JSONDecodeError:
            self.bad_json += 1
            return
        if not isinstance(obj, dict):
            self.bad_json += 1
            return
        self.data_events += 1
        if self.api == 'responses':
            self._responses_event(obj)
        else:
            self._chat_event(obj)

    def _error(self, detail: object) -> None:
        self.errors.append(detail if isinstance(detail, str) else json.dumps(detail))
        self.records.append({'kind': 'error', 'detail': detail})

    def _delta(self, content: str, obj: dict[str, Any], event_type: str | None) -> None:
        self.deltas.append(content)
        self.records.append(
            {
                'kind': 'delta',
                'index': self.lines,
                'event_type': event_type,
                'content': content,
                'provider': obj.get('provider'),
                'model': obj.get('model'),
            }
        )

    def _chat_event(self, obj: dict[str, Any]) -> None:
        if 'error' in obj:
            self._error(obj['error'])
            return
        content = None
        choices = obj.get('choices')
        if isinstance(choices, list) and choices and isinstance(choices[0], dict):
            delta = choices[0].get('delta')
            if isinstance(delta, dict):
                content = delta.get('content')
        if isinstance(content, str):
            self._delta(content, obj, None)
        else:
            self.records.append(
                {'kind': 'data', 'provider': obj.get('provider'), 'model': obj.get('model')}
            )

    def _responses_event(self, obj: dict[str, Any]) -> None:
        etype = obj.get('type') or self._event
        self.records.append({'kind': 'event', 'event_type': etype})
        if etype == RESPONSES_DELTA and isinstance(obj.get('delta'), str):
            self._delta(obj['delta'], obj, etype)
        elif etype == RESPONSES_DONE:
            self.done = True
        elif etype in RESPONSES_ERRORS or 'error' in obj:
            self.done = True
            resp = obj.get('response')
            nested = resp.get('error') if isinstance(resp, dict) else None
            self._error(nested or obj.get('error') or obj.get('message') or obj)
