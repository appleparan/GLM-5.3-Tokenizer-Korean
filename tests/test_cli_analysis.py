import json
from pathlib import Path

import pytest

from glm_ko_tok import cli
from glm_ko_tok.loader import TokenizerNotFoundError


@pytest.fixture(autouse=True)
def _patch_loader(fake_tk, monkeypatch):
    monkeypatch.setattr(cli, 'load_tokenizer', lambda _d: fake_tk)


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


def test_fetch_command(monkeypatch, tmp_path: Path, capsys):
    monkeypatch.setattr(cli, 'fetch_tokenizer', lambda repo, d: [Path(d) / repo])
    assert cli.main(['fetch', '--repo', 'x/y', '--dir', str(tmp_path)]) == 0
    assert 'x/y' in capsys.readouterr().out


def test_missing_tokenizer_message(monkeypatch, capsys):
    def boom(_d):
        msg = 'run glm-ko-tok fetch'
        raise TokenizerNotFoundError(msg)

    monkeypatch.setattr(cli, 'load_tokenizer', boom)
    assert cli.main(['analyze', 'a']) == 1
    assert 'glm-ko-tok fetch' in capsys.readouterr().err
