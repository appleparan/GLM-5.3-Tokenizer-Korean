import base64
import json
from pathlib import Path

import httpx
import pytest

from glm_ko_tok import cli, probe
from glm_ko_tok.probe import ProbeConfigError, ProbeError, build_config, run_probe

FFFD = '\ufffd'
SECRET = 'sk-super-secret'  # noqa: S105


def sse_chat(*contents: str, extra: dict | None = None) -> bytes:
    out = b''
    for c in contents:
        obj = {'choices': [{'delta': {'content': c}}], **(extra or {})}
        out += b'data: ' + json.dumps(obj, ensure_ascii=False).encode() + b'\n\n'
    return out


def make_transport(chunks: list[bytes], status: int = 200, seen: list | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(
            status,
            headers={
                'content-type': 'text/event-stream',
                'x-request-id': 'r1',
                'x-api-key': 'leak',
                'authorization': 'leak',
            },
            content=iter(chunks),
        )

    return httpx.MockTransport(handler)


def cfg(
    env: dict | None = None,
    *,
    target: str = 'vllm',
    base_url: str | None = None,
    api_key_env: str | None = None,
    api: str = 'chat',
    max_tokens: int = 256,
    providers: list[str] | None = None,
):
    return build_config(
        target=target,
        model='m',
        prompt='hi',
        env=env or {},
        base_url=base_url,
        api_key_env=api_key_env,
        api=api,
        max_tokens=max_tokens,
        providers=providers or [],
    )


def test_chat_basic_counts():
    cf = cfg()
    res = run_probe(cf, transport=make_transport([sse_chat('안', '녕') + b'data: [DONE]\n\n']))
    assert res.deltas == 2
    assert res.text == '안녕'
    assert res.fffd_in_deltas == 0
    assert res.fffd_in_raw == 0
    assert res.boundary_splits == 0
    assert res.done


def test_chunk_boundary_splits_hangul():
    data = sse_chat('한') + b'data: [DONE]\n\n'
    cut = data.index('한'.encode()) + 1
    res = run_probe(cfg(), transport=make_transport([data[:cut], data[cut:]]))
    assert res.boundary_splits == 1
    assert res.chunks == 2
    assert res.text == '한'


def test_server_already_sends_fffd():
    data = sse_chat(FFFD + 'a') + b'data: [DONE]\n\n'
    res = run_probe(cfg(), transport=make_transport([data]))
    assert res.fffd_in_deltas == 1
    assert res.fffd_in_raw == 1


def test_escaped_fffd_counts_in_delta_not_raw():
    data = b'data: {"choices":[{"delta":{"content":"\\ufffd"}}]}\n\n'
    res = run_probe(cfg(), transport=make_transport([data]))
    assert res.fffd_in_deltas == 1
    assert res.fffd_in_raw == 0


def test_comment_keepalive_and_done(tmp_path: Path):
    data = b': OPENROUTER PROCESSING\n\n' + sse_chat('a') + b'data: [DONE]\n\n'
    out = tmp_path / 'r' / 'x.jsonl'
    res = run_probe(cfg(), out=out, transport=make_transport([data]))
    assert res.comments == 1
    assert res.deltas == 1
    assert res.done
    recs = [json.loads(ln) for ln in out.read_text(encoding='utf-8').splitlines()]
    kinds = [r['kind'] for r in recs]
    assert kinds[0] == 'header'
    assert 'comment' in kinds
    assert kinds[-1] == 'summary'
    comment = next(r for r in recs if r['kind'] == 'comment')
    assert base64.b64decode(comment['raw_b64']) == b': OPENROUTER PROCESSING'


def test_jsonl_records_raw_lines_and_provider_model(tmp_path: Path):
    data = sse_chat('a', extra={'provider': 'Z.AI', 'model': 'z-ai/glm'})
    out = tmp_path / 'x.jsonl'
    run_probe(cfg(), out=out, transport=make_transport([data]))
    recs = [json.loads(ln) for ln in out.read_text(encoding='utf-8').splitlines()]
    d = next(r for r in recs if r['kind'] == 'delta')
    assert d['provider'] == 'Z.AI'
    assert d['model'] == 'z-ai/glm'
    assert d['content'] == 'a'
    line = next(r for r in recs if r['kind'] == 'line')
    assert base64.b64decode(line['raw_b64']).decode().startswith('data: ')


def test_header_record_drops_secrets(tmp_path: Path):
    out = tmp_path / 'x.jsonl'
    cf = cfg({'OPENAI_API_KEY': SECRET})
    run_probe(cf, out=out, transport=make_transport([sse_chat('a')]))
    text = out.read_text(encoding='utf-8')
    assert SECRET not in text
    assert 'leak' not in text
    header = json.loads(text.splitlines()[0])
    assert header['target'] == 'vllm'
    assert header['model'] == 'm'
    assert header['base_url'] == 'http://localhost:8000/v1'
    assert header['request']['stream'] is True
    assert header['response_headers']['x-request-id'] == 'r1'


def test_error_object_in_data_is_reported():
    data = b'data: {"error": {"message": "boom", "code": 500}}\n\n'
    res = run_probe(cfg(), transport=make_transport([data]))
    assert res.errors
    assert 'boom' in res.errors[0]


def test_bad_json_and_trailing_line_without_newline():
    data = b'data: not-json\n\n' + b'data: {"choices":[{"delta":{"content":"z"}}]}'
    res = run_probe(cfg(), transport=make_transport([data]))
    assert res.bad_json == 1
    assert res.text == 'z'


def test_http_error_raises_probe_error():
    tr = httpx.MockTransport(lambda _r: httpx.Response(401, text='nope'))
    with pytest.raises(ProbeError, match='401'):
        run_probe(cfg(), transport=tr)


def test_vllm_without_key_sends_no_auth_header():
    seen: list = []
    run_probe(cfg(), transport=make_transport([sse_chat('a')], seen=seen))
    assert 'authorization' not in seen[0].headers
    assert seen[0].url == 'http://localhost:8000/v1/chat/completions'


def test_vllm_base_url_from_env_and_key_sent():
    seen: list = []
    cf = cfg({'OPENAI_BASE_URL': 'http://h:9/v1', 'OPENAI_API_KEY': SECRET})
    run_probe(cf, transport=make_transport([sse_chat('a')], seen=seen))
    assert str(seen[0].url) == 'http://h:9/v1/chat/completions'
    assert seen[0].headers['authorization'] == f'Bearer {SECRET}'


def test_openrouter_requires_key_without_leaking():
    with pytest.raises(ProbeConfigError, match='OPENROUTER_API_KEY'):
        cfg(target='openrouter')


def test_openrouter_defaults_and_optional_headers():
    seen: list = []
    env = {
        'OPENROUTER_API_KEY': SECRET,
        'OPENROUTER_REFERER': 'https://example.com',
        'OPENROUTER_TITLE': 'probe',
    }
    cf = cfg(env, target='openrouter')
    run_probe(cf, transport=make_transport([sse_chat('a')], seen=seen))
    req = seen[0]
    assert str(req.url) == 'https://openrouter.ai/api/v1/chat/completions'
    assert req.headers['http-referer'] == 'https://example.com'
    assert req.headers['x-title'] == 'probe'


def test_openrouter_omits_optional_headers_when_unset():
    seen: list = []
    cf = cfg({'OPENROUTER_API_KEY': SECRET}, target='openrouter')
    run_probe(cf, transport=make_transport([sse_chat('a')], seen=seen))
    assert 'http-referer' not in seen[0].headers
    assert 'x-title' not in seen[0].headers


def test_explicit_overrides_beat_preset():
    cf = cfg({'MYKEY': 'k'}, target='openrouter', base_url='http://x:1/v1', api_key_env='MYKEY')
    assert cf.base_url == 'http://x:1/v1'


def test_provider_body_field():
    seen: list = []
    cf = cfg(providers=['Z.AI', 'Novita'])
    run_probe(cf, transport=make_transport([sse_chat('a')], seen=seen))
    body = json.loads(seen[0].content)
    assert body['provider'] == {'order': ['Z.AI', 'Novita'], 'allow_fallbacks': False}
    assert body['stream'] is True
    assert body['messages'][0]['content'] == 'hi'


def test_no_provider_field_by_default():
    seen: list = []
    run_probe(cfg(), transport=make_transport([sse_chat('a')], seen=seen))
    assert 'provider' not in json.loads(seen[0].content)


@pytest.mark.parametrize('url', ['ftp://x/v1', 'localhost:8000', 'file:///etc/passwd', ''])
def test_invalid_url_rejected(url):
    with pytest.raises(ProbeConfigError, match='http'):
        cfg(base_url=url)


def sse_resp(*deltas: str) -> bytes:
    out = b''
    for d in deltas:
        obj = {'type': 'response.output_text.delta', 'delta': d}
        out += (
            b'event: response.output_text.delta\ndata: '
            + json.dumps(obj, ensure_ascii=False).encode()
            + b'\n\n'
        )
    return out


def test_responses_mode_basic(tmp_path: Path):
    seen: list = []
    done = b'event: response.completed\ndata: {"type":"response.completed"}\n\n'
    data = (
        b'event: response.created\ndata: {"type":"response.created"}\n\n'
        + sse_resp('안', '녕')
        + done
    )
    out = tmp_path / 'r.jsonl'
    cf = cfg(api='responses', max_tokens=5)
    res = run_probe(cf, out=out, transport=make_transport([data], seen=seen))
    body = json.loads(seen[0].content)
    assert str(seen[0].url).endswith('/responses')
    assert body == {'model': 'm', 'input': 'hi', 'stream': True, 'max_output_tokens': 5}
    assert res.text == '안녕'
    assert res.deltas == 2
    assert res.done
    recs = [json.loads(ln) for ln in out.read_text(encoding='utf-8').splitlines()]
    types = [r.get('event_type') for r in recs if r['kind'] in ('delta', 'event')]
    assert 'response.created' in types
    assert 'response.completed' in types


def test_responses_ignores_other_event_text_and_splits_char():
    other = b'data: {"type":"response.reasoning_text.delta","delta":"SECRET"}\n\n'
    data = other + sse_resp('한') + b'data: {"type":"response.completed"}\n\n'
    cut = data.index('한'.encode()) + 2
    res = run_probe(cfg(api='responses'), transport=make_transport([data[:cut], data[cut:]]))
    assert res.text == '한'
    assert res.boundary_splits == 1
    assert res.fffd_in_deltas == 0


def test_responses_failed_event_reported():
    data = b'data: {"type":"response.failed","response":{"error":{"message":"bad"}}}\n\n'
    res = run_probe(cfg(api='responses'), transport=make_transport([data]))
    assert res.done
    assert 'bad' in res.errors[0]


def test_responses_error_event_reported():
    data = b'event: error\ndata: {"type":"error","message":"oops"}\n\n'
    res = run_probe(cfg(api='responses'), transport=make_transport([data]))
    assert 'oops' in res.errors[0]


def test_format_mentions_key_numbers():
    res = run_probe(cfg(), transport=make_transport([sse_chat('a')]))
    text = res.format()
    assert 'chunks' in text
    assert 'U+FFFD' in text


@pytest.fixture
def _mock_run(monkeypatch):
    def fake(config, out=None):
        return run_probe(config, out=out, transport=make_transport([sse_chat('한')]))

    monkeypatch.setattr(probe, 'run_probe', fake)


@pytest.mark.usefixtures('_mock_run')
def test_cli_probe(capsys, tmp_path: Path, monkeypatch):
    monkeypatch.delenv('OPENAI_BASE_URL', raising=False)
    out = tmp_path / 'o.jsonl'
    argv = ['probe', '--model', 'm', '--prompt', 'hi', '--out', str(out), '--provider', 'A']
    assert cli.main(argv) == 0
    assert 'chunks' in capsys.readouterr().out
    assert out.exists()


@pytest.mark.usefixtures('_mock_run')
def test_cli_probe_missing_openrouter_key(capsys, monkeypatch):
    monkeypatch.delenv('OPENROUTER_API_KEY', raising=False)
    argv = ['probe', '--target', 'openrouter', '--model', 'm', '--prompt', 'hi']
    assert cli.main(argv) == 2
    assert 'OPENROUTER_API_KEY' in capsys.readouterr().err
