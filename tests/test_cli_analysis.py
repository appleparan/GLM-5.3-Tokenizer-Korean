import json
from pathlib import Path

import pytest

from glm_ko_tok import cli
from glm_ko_tok.loader import LoadedModel, TokenizerNotFoundError
from glm_ko_tok.models import MODELS


@pytest.fixture(autouse=True)
def _patch_loader(fake_tk, monkeypatch):
    monkeypatch.setattr(
        cli, 'load_model', lambda key, _r: LoadedModel(MODELS[key], fake_tk, Path('nowhere'))
    )


def test_analyze_text(capsys):
    assert cli.main(['analyze', '한a']) == 0
    out = capsys.readouterr().out
    assert 'tokens=3' in out
    assert '959c' in out


def test_analyze_json(capsys):
    assert cli.main(['analyze', '한a', '--json']) == 0
    data = json.loads(capsys.readouterr().out)
    assert data['summary']['split_chars'] == 1


def test_analyze_file_per_line(tmp_path: Path, capsys):
    f = tmp_path / 's.txt'
    f.write_text('# group\n한a\n\n국\n', encoding='utf-8')
    assert cli.main(['analyze', '--file', str(f), '--per-line']) == 0
    out = capsys.readouterr().out
    assert '한a' in out
    assert '국' in out
    assert '# group' not in out
    assert 'TOTAL' in out


def test_analyze_requires_input(capsys):
    assert cli.main(['analyze']) == 2
    assert 'TEXT or --file' in capsys.readouterr().err


def test_coverage_json(capsys):
    assert cli.main(['coverage', '--json']) == 0
    assert json.loads(capsys.readouterr().out)['all']['total'] == 11172


def test_coverage_text(capsys):
    assert cli.main(['coverage']) == 0
    assert 'KS X 1001' in capsys.readouterr().out


def test_fetch_command_single_and_all(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setattr(cli, 'fetch_model', lambda spec, root: [Path(root) / spec.key / 'f'])
    assert cli.main(['fetch', '--root', str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert 'glm-5.3:' in out
    assert 'kimi-k3' not in out
    assert cli.main(['fetch', '--model', 'all', '--root', str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert all(f'{k}:' in out for k in MODELS)


def test_unknown_model_is_an_error(capsys):
    assert cli.main(['coverage', '--model', 'nope']) == 2
    assert 'unknown model' in capsys.readouterr().err


def test_multi_model_headers_and_json(capsys):
    assert cli.main(['coverage', '--model', 'glm-5.3', '--model', 'kimi-k3']) == 0
    out = capsys.readouterr().out
    assert '== glm-5.3 ==' in out
    assert '== kimi-k3 ==' in out
    assert cli.main(['analyze', '한a', '--model', 'all', '--json']) == 0
    assert set(json.loads(capsys.readouterr().out)) == set(MODELS)


def test_missing_tokenizer_message(monkeypatch, capsys):
    def boom(_k, _r):
        msg = 'run glm-ko-tok fetch'
        raise TokenizerNotFoundError(msg)

    monkeypatch.setattr(cli, 'load_model', boom)
    assert cli.main(['analyze', 'a']) == 1
    assert 'glm-ko-tok fetch' in capsys.readouterr().err
