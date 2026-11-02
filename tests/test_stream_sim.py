import codecs
import json
from pathlib import Path

import pytest

from glm_ko_tok import cli
from glm_ko_tok.loader import LoadedModel
from glm_ko_tok.models import MODELS
from glm_ko_tok.stream_sim import simulate_stream

FFFD = '�'


def test_incremental_decoder_on_split_bytes():
    dec = codecs.getincrementaldecoder('utf-8')('replace')
    data = '한'.encode()
    assert dec.decode(data[:1]) == ''
    assert dec.decode(data[1:], final=True) == '한'


def test_naive_breaks_incremental_recovers(fake_tk):
    report = simulate_stream(fake_tk, '한a')
    by = {r.name: r for r in report.results}
    assert report.truth == '한a'
    assert FFFD in by['naive'].output
    assert not by['naive'].equals_truth
    assert by['naive'].lossy
    assert by['incremental'].output == '한a'
    assert by['incremental'].equals_truth
    assert not by['incremental'].lossy
    assert by['incremental'].fffd_count == 0


def test_tiktoken_style_backend_skips_decode_stream_and_naive_breaks(fake_tk):
    report = simulate_stream(fake_tk, '한')
    by = {r.name: r for r in report.results}
    assert by['decode_stream'].skipped
    assert 'HF' in by['decode_stream'].note
    assert by['naive'].fffd_count == 3


def test_decode_stream_skipped_for_fake(fake_tk):
    by = {r.name: r for r in simulate_stream(fake_tk, 'a').results}
    assert by['decode_stream'].skipped


def test_ascii_all_equal(fake_tk):
    report = simulate_stream(fake_tk, 'abc')
    assert all(r.equals_truth for r in report.results if not r.skipped)


def test_truth_with_native_fffd_is_not_lossy(fake_tk):
    report = simulate_stream(fake_tk, FFFD)
    by = {r.name: r for r in report.results}
    assert by['incremental'].equals_truth
    assert not by['incremental'].lossy


def test_report_json_and_format(fake_tk):
    report = simulate_stream(fake_tk, '한')
    assert json.loads(report.to_json())['results'][0]['name'] == 'naive'
    assert 'naive' in report.format()


@pytest.fixture
def _patched(fake_tk, monkeypatch):
    monkeypatch.setattr(
        cli, 'load_model', lambda key, _r: LoadedModel(MODELS[key], fake_tk, Path('nowhere'))
    )


@pytest.mark.usefixtures('_patched')
def test_cli_stream_sim_text(capsys):
    assert cli.main(['stream-sim', '한a']) == 0
    assert 'incremental' in capsys.readouterr().out


@pytest.mark.usefixtures('_patched')
def test_cli_stream_sim_per_line(tmp_path: Path, capsys):
    f = tmp_path / 's.txt'
    f.write_text('# c\n한a\nabc\n', encoding='utf-8')
    assert cli.main(['stream-sim', '--file', str(f), '--per-line']) == 0
    out = capsys.readouterr().out
    assert 'TOTAL' in out
    assert '한a' in out


@pytest.mark.usefixtures('_patched')
def test_cli_stream_sim_requires_input(capsys):
    assert cli.main(['stream-sim']) == 2


@pytest.mark.usefixtures('_patched')
def test_cli_per_line_total_shows_dash_when_decode_stream_skipped(tmp_path: Path, capsys):
    f = tmp_path / 's.txt'
    f.write_text('한a\n', encoding='utf-8')
    assert cli.main(['stream-sim', '--file', str(f), '--per-line']) == 0
    total = [ln for ln in capsys.readouterr().out.splitlines() if ln.startswith('TOTAL')][0]
    assert total.split()[-1] == '-'
