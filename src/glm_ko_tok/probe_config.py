"""Probe configuration: target presets, URL validation, request building."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

OPENROUTER_BASE_URL = 'https://openrouter.ai/api/v1'
LOCAL_BASE_URL = 'http://localhost:8000/v1'
TARGETS = ('vllm', 'openrouter')
APIS = ('chat', 'responses')


class ProbeConfigError(ValueError):
    """Raised for invalid probe settings (URL, missing key)."""


@dataclass(frozen=True)
class ProbeConfig:
    """Everything needed to send one probe request."""

    target: str
    api: str
    base_url: str
    model: str
    prompt: str
    max_tokens: int
    providers: tuple[str, ...] = ()
    api_key: str | None = field(default=None, repr=False)
    extra_headers: dict[str, str] = field(default_factory=dict)

    @property
    def url(self) -> str:
        """Full endpoint URL."""
        path = 'chat/completions' if self.api == 'chat' else 'responses'
        return f'{self.base_url.rstrip("/")}/{path}'

    def body(self) -> dict[str, Any]:
        """JSON request body (contains no secrets)."""
        if self.api == 'chat':
            body: dict[str, Any] = {
                'model': self.model,
                'messages': [{'role': 'user', 'content': self.prompt}],
                'stream': True,
                'max_tokens': self.max_tokens,
            }
        else:
            body = {
                'model': self.model,
                'input': self.prompt,
                'stream': True,
                'max_output_tokens': self.max_tokens,
            }
        if self.providers:
            body['provider'] = {'order': list(self.providers), 'allow_fallbacks': False}
        return body

    def headers(self) -> dict[str, str]:
        """Request headers, including Authorization when a key is set."""
        headers = {'Content-Type': 'application/json', 'Accept': 'text/event-stream'}
        headers.update(self.extra_headers)
        if self.api_key:
            headers['Authorization'] = f'Bearer {self.api_key}'
        return headers


def validate_url(url: str) -> str:
    """Check that a URL uses http or https.

    Raises:
        ProbeConfigError: If the scheme or host is invalid.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        msg = f'base URL must start with http:// or https:// and have a host: {url!r}'
        raise ProbeConfigError(msg)
    return url


def build_config(
    *,
    target: str,
    model: str,
    prompt: str,
    env: Mapping[str, str],
    base_url: str | None = None,
    api_key_env: str | None = None,
    api: str = 'chat',
    max_tokens: int = 256,
    providers: tuple[str, ...] | list[str] = (),
) -> ProbeConfig:
    """Resolve a target preset plus overrides into a config.

    Args:
        target: `vllm` or `openrouter`.
        model: Model id.
        prompt: User prompt.
        env: Environment mapping (injected for tests).
        base_url: Overrides the preset base URL.
        api_key_env: Overrides the preset key variable name.
        api: `chat` (Chat Completions) or `responses` (Responses API).
        max_tokens: Output token limit.
        providers: OpenRouter upstream providers to pin.

    Returns:
        The resolved config.

    Raises:
        ProbeConfigError: On invalid URL, unknown target/api, or a missing required key.
    """
    if target not in TARGETS or api not in APIS:
        msg = f'unknown target {target!r} or api {api!r}'
        raise ProbeConfigError(msg)
    if target == 'openrouter':
        url = OPENROUTER_BASE_URL if base_url is None else base_url
        key_var = api_key_env or 'OPENROUTER_API_KEY'
    else:
        url = env.get('OPENAI_BASE_URL') or LOCAL_BASE_URL if base_url is None else base_url
        key_var = api_key_env or 'OPENAI_API_KEY'
    key = env.get(key_var) or None
    if key is None and target == 'openrouter':
        msg = f'{key_var} is not set; OpenRouter requires an API key'
        raise ProbeConfigError(msg)
    extra: dict[str, str] = {}
    if target == 'openrouter':
        for header, var in (
            ('HTTP-Referer', 'OPENROUTER_REFERER'),
            ('X-Title', 'OPENROUTER_TITLE'),
        ):
            if env.get(var):
                extra[header] = env[var]
    return ProbeConfig(
        target=target,
        api=api,
        base_url=validate_url(url),
        model=model,
        prompt=prompt,
        max_tokens=max_tokens,
        providers=tuple(providers),
        api_key=key,
        extra_headers=extra,
    )
